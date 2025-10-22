"""
Extract Knowledge Graph from a single document using GPT-5-mini
"""
import os
from openai import OpenAI
from atlas_rag.kg_construction.triple_extraction import ProcessingConfig, KnowledgeGraphExtractor
from atlas_rag.llm_generator.llm_generator import LLMGenerator

# Setup OpenAI client
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),  # Set your API key in environment variable
    base_url="https://api.openai.com/v1"
)

# Use GPT-5 Mini
model_name = "gpt-5-mini"

# Configure for graphmert document
keyword = 'graphmert'
filename_pattern = f'{keyword}.json'
output_directory = f'import/{keyword}'

# Create LLM Generator
triple_generator = LLMGenerator(client, model_name=model_name, backend='openai')

# Configure the extraction pipeline
kg_extraction_config = ProcessingConfig(
    model_path=model_name,
    data_directory="example_data",
    filename_pattern=filename_pattern,
    batch_size_triple=16,  # batch size for triple extraction
    batch_size_concept=16,  # batch size for concept generation
    output_directory=f"{output_directory}",
    max_new_tokens=2048,
    max_workers=3,
    remove_doc_spaces=True,  # For removing duplicated spaces in the document text
    include_concept=False,  # Skip concept generation to reduce API calls
)

# Create the extractor
kg_extractor = KnowledgeGraphExtractor(model=triple_generator, config=kg_extraction_config)

print("="*60)
print("Starting Knowledge Graph Extraction")
print("="*60)
print(f"Document: {filename_pattern}")
print(f"Model: {model_name}")
print(f"Output: {output_directory}")
print(f"Concept Generation: DISABLED (saves ~1700 API calls)")
print("="*60)

# Construct entity&event graph
print("\n[1/5] Extracting triples (LLM Generation)...")
kg_extractor.run_extraction()

# Convert Triples Json to CSV
print("\n[2/5] Converting JSON to CSV...")
kg_extractor.convert_json_to_csv()

# Concept Generation (DISABLED - set include_concept=True to enable)
# print("\n[3/5] Generating concepts (LLM Generation)...")
# kg_extractor.generate_concept_csv_temp(batch_size=64)

# Create Concept CSV (DISABLED - set include_concept=True to enable)
# print("\n[4/5] Creating concept CSV...")
# kg_extractor.create_concept_csv()

# Convert csv to graphml for networkx
print("\n[3/5] Converting to GraphML...")
kg_extractor.convert_to_graphml()

print("\n" + "="*60)
print("SUCCESS! Knowledge Graph Construction Complete")
print("="*60)
print(f"\nOutput directory: {output_directory}")
print("\nGenerated files:")
print("  - kg_extraction/*.json  (raw extraction results)")
print("  - triples_csv/*.csv     (entity, event, and relation CSVs)")
print("  - kg_graphml/*.pkl      (graph structure for Neo4j)")
print("\nNext step: Run import_to_neo4j_with_merge.py to load into Neo4j")

