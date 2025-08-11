import numpy as np
from atlas_rag.vectorstore.embedding_model import BaseEmbeddingModel
from atlas_rag.llm_generator.llm_generator import LLMGenerator
from atlas_rag.llm_generator.prompt.tog_prompt import *
from typing import Optional
from atlas_rag.retriever.base import BaseEdgeRetriever
from atlas_rag.retriever.inference_config import InferenceConfig
import numpy as np
import json_repair
import networkx as nx
from networkx import DiGraph
from collections import defaultdict
import json

class TogRetriever(BaseEdgeRetriever):
    def __init__(self, llm_generator:LLMGenerator, sentence_encoder:BaseEmbeddingModel, data:dict, inference_config:InferenceConfig = None):
        self.llm_generator = llm_generator
        self.reranker = sentence_encoder
        self.node_embeddings = data["node_embeddings"]
        if isinstance(self.node_embeddings, list):
            self.node_embeddings = np.array(self.node_embeddings)
        self.node_list = data["node_list"]
        self.KG = data["KG"]
        self.node_id_to_attr_id = {node_id: data['id'] for node_id, data in self.KG.nodes(data=True) if 'id' in data}
        self.attr_id_to_node_id = {data['id']: node_id for node_id, data in self.KG.nodes(data=True) if 'id' in data}
        self.config = inference_config if inference_config is not None else InferenceConfig()

    def ner(self, text):
        messages = [
            {
                "role": "system",
                "content": "Extract the topic entities from the following question and output them as a JSON object in the format: {\"entities\": [\"entity1\", \"entity2\", ...]}"
            },
            {
                "role": "user",
                "content": f"Identify starting points for reasoning within a knowledge graph to find relevant information and clues for answering the question. Extract the topic entities from: {text}"
            }
        ]
        response = self.llm_generator.generate_response(messages)
        
        # Parse the response to ensure it is a valid JSON object
        entities_json = json_repair.loads(response)
        if "entities" not in entities_json or not isinstance(entities_json["entities"], list):
            return {}
        return entities_json

    def topic_prune(self, query, entities):        
        # Step 2: If no entities are retrieved, return an empty dictionary
        if not entities:
            return {}
        
        if len(entities) < self.config.Wmax:
            return {"entities": entities}
        
        # Step 3: Prepare a prompt for the LLM to analyze the suitability of each entity
        analysis_prompt = TOPIC_PRUNE_PROMPT % (query, entities)
        
        # Step 4: Generate the LLM response to analyze and prune the entities
        messages = [
            {
                "role": "system",
                "content": "You are a reasoning assistant tasked with pruning topic entities for a knowledge graph query. Provide a JSON-formatted output containing only the entities suitable as starting points for reasoning, based on the provided question and topic entities."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ]
        
        response = self.llm_generator.generate_response(messages, temperature=self.config.temperature_exploration)
        
        # Step 5: Parse the response to ensure it is a valid JSON dictionary
        pruned_entities = json_repair.loads(response)
        if not isinstance(pruned_entities, dict):
            return {}
        return pruned_entities

    def relation_prune_combination(self, query, entities_relation: dict):
        # only prompt with entities with number of relations larger than self.config.width
        # For those that are less than self.config.width, we keep all relations
        entities_relation_less = {entity: relations for entity, relations in entities_relation.items() if len(relations) <= self.config.Wmax}
        entities_relation_more = {entity: relations for entity, relations in entities_relation.items() if len(relations) > self.config.Wmax}

        # Step 1: Prepare the prompt for the LLM
        entities_prompt = "\n".join(
            [
                f'Entity: "{entity}"\nAvailable Relations: {relations}'
                for entity, relations in entities_relation_more.items()
            ]
        )
        analysis_prompt = RELATION_PRUNE_PROMPT % (self.config.Wmax, self.config.Wmax) + f"\nQuestion: {query}\n{entities_prompt}"

        # Step 2: Generate the LLM response to analyze and prune the relations
        messages = [
            {
                "role": "system",
                "content": "You are a reasoning assistant tasked with pruning relations for entities in a knowledge graph query. Provide a JSON-formatted output containing the most relevant relations for each entity."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ]

        response = self.llm_generator.generate_response(messages, temperature=self.config.temperature_exploration)

        # Step 3: Parse the response to ensure it is a valid JSON dictionary
        try:
            pruned_relations = json_repair.loads(response)
            if not isinstance(pruned_relations, list):
                return entities_relation
            # combine the pruned relations with those that were less than self.config.width
            if not all("entity" in item and "relations" in item for item in pruned_relations):
                return entities_relation
            return {item["entity"]: item["relations"] for item in pruned_relations if "entity" in item and "relations" in item} | entities_relation_less
        except Exception as e:
            print(f"Error parsing relation prune response: {e}")
            return entities_relation

    def retrieve_topk_nodes(self, query):
        # Step 1: Extract topic entities using the ner method
        entities_json = self.ner(query)
        entities = entities_json.get("entities", [])
        if not entities:
            entities = [query]
        else:
            if self.config.topic_prune:
                entities_json = self.topic_prune(query, entities)
                entities = entities_json.get("entities", [entities])
        topk_nodes = []
        entities_not_in_kg = []
        # map entities into KG's nodes
        entities = [str(e) for e in entities]
        for entity in entities:
            if entity in self.KG.nodes:
                topk_nodes.append(entity)
            else:
                entities_not_in_kg.append(entity)

        if entities_not_in_kg:
            query_embeddings = self.reranker.encode(entities_not_in_kg)
            document_embeddings = self.node_embeddings
            sim_scores = query_embeddings @ document_embeddings.T
            # get the top-1 similar node
            index = np.argmax(sim_scores, axis=1)
            assert len(index) == len(entities_not_in_kg), "Index length does not match entities_not_in_kg length"
            for i in index:
                top_node = self.KG.nodes[self.node_list[i]]['id']
                topk_nodes.append(top_node)
        return topk_nodes

    def retrieve(self, question, topN = 5) -> str:
        initial_nodes = self.retrieve_topk_nodes(question)
        E = initial_nodes
        P = [[e] for e in E]
        D = 0
        answerable = False
        while D <= self.config.Dmax:
            P = self.search(question, P)
            P = self.prune(question, P, topN)
            answerable, answer = self.reasoning(question, P)
            if answerable:
                break
            D += 1
            
        return ["->".join(path) for path in P], ["NA" for i in range(len(P))]

    def search(self, query, P):
        new_paths = []
        entity_relation_dict = defaultdict(list)

        # Step 1: Collect relations for each tail entity
        for path in P:
            tail_entity = path[-1]
            # Collect successors
            tail_entity_id = self.attr_id_to_node_id.get(tail_entity)
            for neighbor in self.KG.successors(tail_entity_id):
                relation = self.KG.edges[(tail_entity_id, neighbor)]["relation"]
                if relation not in entity_relation_dict[tail_entity]:
                    entity_relation_dict[tail_entity].append(relation)
            # Collect predecessors
            for neighbor in self.KG.predecessors(tail_entity_id):
                relation = self.KG.edges[(neighbor, tail_entity_id)]["relation"]
                if relation not in entity_relation_dict[tail_entity]:
                    entity_relation_dict[tail_entity].append(relation)

        # Step 2: Perform relation pruning if enabled
        if self.config.remove_unnecessary_rel:
            entity_relation_dict = self.relation_prune_combination(query, entity_relation_dict)

        # Step 3: Expand paths using pruned relations
        for path in P:
            tail_entity = path[-1]
            if tail_entity not in entity_relation_dict:
                new_paths.append(path)  # Keep the path if no relations are available for the tail entity
                continue  # Skip if no relations are available for the tail entity

            # Expand with successors
            tail_entity_id = self.attr_id_to_node_id.get(tail_entity)
            for neighbor in self.KG.successors(tail_entity_id):
                relation = self.KG.edges[(tail_entity_id, neighbor)]["relation"]
                if relation in entity_relation_dict[tail_entity] and neighbor not in path:
                    neighbor = self.node_id_to_attr_id.get(neighbor)
                    new_paths.append(path + [relation, neighbor])
            # Expand with predecessors
            for neighbor in self.KG.predecessors(tail_entity_id):
                relation = self.KG.edges[(neighbor, tail_entity_id)]["relation"]
                if relation in entity_relation_dict[tail_entity] and neighbor not in path:
                    neighbor = self.node_id_to_attr_id.get(neighbor)
                    new_paths.append(path + [relation, neighbor])

        return new_paths

    def prune(self, query, P, topN):
        # construct KG path string
        all_paths = []
        for path in P:
            triples = []
            for i in range(0, len(path)-2, 2):
                s = path[i]
                r = path[i+1]
                o = path[i+2]
                triples.append((s, r, o))
            triples_string = ". ".join([f"({s}, {r}, {o})" for s, r, o in triples])
            # consturct the query prompt
            all_paths.append(triples_string)
        # use reranker to score the paths
        query = f"Instruct: {RERANKER_RANK_PATH_PROMPT}\nQuery: {query}"
        embeddings = self.reranker.encode([query] + all_paths)
        query_embeddings = embeddings[:len([query])]
        document_embeddings = embeddings[len([query]):]
        ratings = query_embeddings @ document_embeddings.T
        ratings = ratings.flatten().tolist()
        sorted_paths = [path for _, path in sorted(zip(ratings, P), reverse=True)]
        return sorted_paths[:topN]

    def reasoning(self, query, P):
        all_paths = []
        for path in P:
            triples = []
            for i in range(0, len(path)-2, 2):
                s = path[i]
                r = path[i+1]
                o = path[i+2]
                triples.append((s, r, o))
            triples_string = ". ".join([f"({s}, {r}, {o})" for s, r, o in triples])
            # consturct the query prompt
            all_paths.append(triples_string)
        all_paths_string = "\n".join(all_paths)
        prompt = REASONING_PROMPT % (query, all_paths_string)
        messages = [
            {"role": "system", "content": "You are a helpful assistant that reasons and answers questions based on the provided knowledge graph context."},
        ]
        messages.extend(REASONING_FEW_SHOT_EXAMPLE)
        messages.append({
            "role": "user",
            "content": prompt
        })
        response = self.llm_generator.generate_response(messages, temperature=self.config.temperature_reasoning)
        result_json = json_repair.loads(response)
        if not isinstance(result_json, dict) or "answer" not in result_json or "is_answerable" not in result_json:
            return False, ""
        is_answerable = result_json.get("is_answerable", False)
        answer = result_json.get("answer", "")
        if is_answerable:
            return True, answer
        return False, ""

    def generate(self, query, P):
        all_paths = []
        for path in P:
            triples = []
            for i in range(0, len(path)-2, 2):
                s = path[i]
                r = path[i+1]
                o = path[i+2]
                triples.append((s, r, o))
            triples_string = ". ".join([f"({s}, {r}, {o})" for s, r, o in triples])
            # consturct the query prompt
            all_paths.append(triples_string)
        all_paths_string = "\n".join(all_paths)
        prompt = ANSWER_GENERATION_PROMPT % (query, all_paths_string)
        messages = [
            {"role": "system", "content": "You are a helpful assistant that reasons and answers questions based on the provided knowledge graph context."},
        ]
        messages.extend(ANSWER_GENERATION_FEW_SHOT_EXAMPLE)
        messages.append({
            "role": "user",
            "content": prompt
        })
        response = self.llm_generator.generate_response(messages, temperature=self.config.temperature_reasoning)
        result_json = json_repair.loads(response)
        if not isinstance(result_json, dict) or "answer" not in result_json:
            return response
        answer = result_json.get("answer", "")
        return answer