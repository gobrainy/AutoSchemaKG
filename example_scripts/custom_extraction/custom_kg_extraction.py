from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor
from atlas_rag.kg_construction.triple_config import ProcessingConfig
from atlas_rag.llm_generator import LLMGenerator
from openai import OpenAI
from configparser import ConfigParser
import argparse
parser = argparse.ArgumentParser(description="Custom KG Extraction")
parser.add_argument("--keyword", type=str, default="musique", help="Keyword for extraction")
args = parser.parse_args()
# Load OpenRouter API key from config file
config = ConfigParser()
config.read('config.ini')
# model_name = "meta-llama/Llama-3.3-70B-Instruct"
# connection = AIProjectClient(
#     endpoint=config["urls"]["AZURE_URL"],
#     credential=DefaultAzureCredential(),
# )
# client = connection.inference.get_azure_openai_client(api_version="2024-12-01-preview")
client = OpenAI(base_url="http://0.0.0.0:8129/v1", api_key="EMPTY")
triple_generator = LLMGenerator(client=client, model_name="Qwen/Qwen2.5-7B-Instruct")

# model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
# model_name = "meta-llama/Llama-3.2-3B-Instruct"
# client = pipeline(
#     "text-generation",
#     model=model_name,
#     device_map="auto",
# )
filename_pattern = args.keyword
output_directory = f'benchmark_data/autograph/{filename_pattern}'
# triple_generator = LLMGenerator(client, model_name=model_name)
model_name = "Qwen/Qwen2.5-7B-Instruct"
kg_extraction_config = ProcessingConfig(
      model_path=model_name,
      data_directory=f'{output_directory}',
      filename_pattern=filename_pattern,
      batch_size_triple=16,
      batch_size_concept=16,
      output_directory=f"{output_directory}",
      max_new_tokens=8192,
      max_workers=5,
      remove_doc_spaces=True, # For removing duplicated spaces in the document text
      include_concept=False, # Whether to include concept nodes and edges in the knowledge graph
      triple_extraction_prompt_path='benchmark_data/autograph/custom_prompt.json',
      triple_extraction_schema_path='benchmark_data/autograph/custom_schema.json',
      record=True, # Whether to record the results in a JSON file
)
kg_extractor = KnowledgeGraphExtractor(model=triple_generator, config=kg_extraction_config)
# construct entity&event graph
kg_extractor.run_extraction()
# Convert Triples Json to CSV
kg_extractor.convert_json_to_csv()
# convert csv to graphml for networkx
kg_extractor.convert_to_graphml()