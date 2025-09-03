from azure.ai.projects import AIProjectClient
from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor
from atlas_rag.kg_construction.triple_config import ProcessingConfig
from azure.identity import DefaultAzureCredential
from atlas_rag.llm_generator import LLMGenerator
from configparser import ConfigParser
from argparse import ArgumentParser
from openai import OpenAI
import time

parser = ArgumentParser(description="Generate knowledge graph slices from text data.")
parser.add_argument("--slice", type=int, help="Slice number to process.", default=0)
parser.add_argument("--total_slices", type=int, help="Total number of slices to process.", default=1)
args = parser.parse_args()

if __name__ == "__main__":
    keyword = 'cc_en_head'
    config = ConfigParser()
    config.read('config.ini')
    # Added support for Azure Foundry. To use it, please do az-login in cmd first.
    # model_name = "DeepSeek-V3-0324"
    # connection = AIProjectClient(
    #     endpoint=config["urls"]["AZURE_URL"],
    #     credential=DefaultAzureCredential(),
    # )
    # client = connection.inference.get_azure_openai_client(api_version="2024-12-01-preview")
    # model_name = "meta-llama/Llama-3.3-70B-Instruct"
    # model_name = "Qwen/Qwen3-8B"
    model_name = "meta-llama/Llama-3.3-70B-Instruct"
    # model_name = "Qwen/Qwen3-8B"
    # model_name = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    client = OpenAI(
        base_url="http://localhost:8122/v1",
        api_key="EMPTYKEY",
    )
    triple_generator = LLMGenerator(client, model_name=model_name)
    if '/' in model_name:
        model_name = model_name.split('/')[-1]
    start_time = time.time()
    kg_extraction_config = ProcessingConfig(
        model_path=model_name,
        data_directory="/data/AutoSchema",
        filename_pattern=keyword,
        batch_size_triple=4,
        batch_size_concept=64,
        output_directory=f'/data/AutoSchema/{model_name}',
        current_shard_triple=args.slice,
        total_shards_triple=args.total_slices,
        record=True,
        max_new_tokens=512,
        benchmark=True
    )
    kg_extractor = KnowledgeGraphExtractor(model=triple_generator, config=kg_extraction_config)
    start_time = time.time()
    kg_extractor.convert_json_to_csv()
    kg_extractor.generate_concept_csv_temp(language='en')
    # Uncomment the following lines to generate concept CSV for other languages
    # kg_extractor.generate_concept_csv_temp(language='zh-HK')
    # kg_extractor.generate_concept_csv_temp(language='zh-CN')
    kg_extractor.create_concept_csv()
    total_time = time.time() - start_time
    print(f"Total time: {total_time:.2f} seconds")