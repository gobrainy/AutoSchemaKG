"""
Import my_document Knowledge Graph to Neo4j
"""
import os
from neo4j import GraphDatabase
import pandas as pd

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "admin2024"

# Data directory
DATA_DIR = "import/my_document"

def clear_database(driver):
    """Clear all existing data"""
    print("Clearing existing data...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Database cleared!")

def import_nodes(driver, csv_path, node_label):
    """Import nodes from CSV"""
    print(f"\nImporting {node_label} nodes from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} nodes")
    
    with driver.session() as session:
        count = 0
        for _, row in df.iterrows():
            # Use name:ID for triple nodes, concept_id:ID for concepts, id:ID for others
            if 'name:ID' in df.columns:
                node_id = row['name:ID']
            elif 'concept_id:ID' in df.columns:
                node_id = row['concept_id:ID']
            elif 'id:ID' in df.columns:
                node_id = row['id:ID']
            else:
                continue
            
            node_type = row.get('type', node_label)
            
            # Determine label based on node type
            if node_label == "Concept":
                label = 'Concept'
            elif node_type == 'event':
                label = 'Event'
            else:
                label = 'Entity'
            
            properties = {'id': node_id}
            
            # Add name if available
            if 'name' in df.columns:
                properties['name'] = str(row['name'])
            else:
                properties['name'] = str(node_id)
            
            # Add all other columns as properties
            for col in df.columns:
                if col not in ['name:ID', 'id:ID', 'concept_id:ID', 'type', ':LABEL', 'name']:
                    val = row[col]
                    if pd.notna(val) and str(val) != '[]':
                        properties[col] = str(val)
            
            # Create node with dynamic label
            query = f"CREATE (n:{label} $props)"
            session.run(query, props=properties)
            count += 1
            
            if count % 100 == 0:
                print(f"  Imported {count} nodes...")
    
    print(f"Successfully imported {count} {node_label} nodes")

def import_text_nodes(driver, csv_path):
    """Import text nodes from CSV"""
    print(f"\nImporting text nodes from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} text nodes")
    
    with driver.session() as session:
        count = 0
        for _, row in df.iterrows():
            text_id = row['text_id:ID']
            original_text = row['original_text']
            
            query = """
            CREATE (n:Text {id: $text_id, original_text: $original_text})
            """
            session.run(query, text_id=text_id, original_text=original_text)
            count += 1
    
    print(f"Successfully imported {count} text nodes")

def import_relationships(driver, csv_path, rel_type):
    """Import relationships from CSV"""
    print(f"\nImporting {rel_type} relationships from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} relationships")
    
    with driver.session() as session:
        count = 0
        for _, row in df.iterrows():
            start_id = row[':START_ID']
            end_id = row[':END_ID']
            
            properties = {}
            for col in df.columns:
                if col not in [':START_ID', ':END_ID', ':TYPE']:
                    val = row[col]
                    if pd.notna(val):
                        properties[col] = str(val)
            
            # Try to create relationship, skip if nodes don't exist
            try:
                query = f"""
                MATCH (a {{id: $start_id}})
                MATCH (b {{id: $end_id}})
                CREATE (a)-[r:{rel_type} $props]->(b)
                """
                session.run(query, start_id=start_id, end_id=end_id, props=properties)
                count += 1
                
                if count % 100 == 0:
                    print(f"  Imported {count} relationships...")
            except:
                pass  # Skip if nodes don't exist
    
    print(f"Successfully imported {count} {rel_type} relationships")

def main():
    print("="*60)
    print("Importing my_document Knowledge Graph to Neo4j")
    print("="*60)
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        # Clear existing data
        clear_database(driver)
        
        # Import nodes
        triples_csv = os.path.join(DATA_DIR, "triples_csv")
        
        # Import entity/event nodes
        nodes_csv = os.path.join(triples_csv, "triple_nodes_my_document.json_from_json_without_emb.csv")
        if os.path.exists(nodes_csv):
            import_nodes(driver, nodes_csv, "Node")
        
        # Import text nodes
        text_nodes_csv = os.path.join(triples_csv, "text_nodes_my_document.json_from_json.csv")
        if os.path.exists(text_nodes_csv):
            import_text_nodes(driver, text_nodes_csv)
        
        # Import relationships
        # Triple relationships (RELATION)
        relations_csv = os.path.join(triples_csv, "triple_edges_my_document.json_from_json_without_emb.csv")
        if os.path.exists(relations_csv):
            import_relationships(driver, relations_csv, "RELATION")
        
        # Source relationships
        sources_csv = os.path.join(triples_csv, "text_edges_my_document.json_from_json.csv")
        if os.path.exists(sources_csv):
            import_relationships(driver, sources_csv, "SOURCE")
        
        # Import concept nodes
        concept_csv = os.path.join(DATA_DIR, "concept_csv")
        
        concept_nodes_csv = os.path.join(concept_csv, "concept_nodes_my_document.json_from_json_with_concept.csv")
        if os.path.exists(concept_nodes_csv):
            import_nodes(driver, concept_nodes_csv, "Concept")
        
        # Concept relationships (HAS_CONCEPT)
        concept_edges_csv = os.path.join(concept_csv, "concept_edges_my_document.json_from_json_with_concept.csv")
        if os.path.exists(concept_edges_csv):
            import_relationships(driver, concept_edges_csv, "HAS_CONCEPT")
        
        print("\n" + "="*60)
        print("Import Complete!")
        print("="*60)
        
        # Get statistics
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY count DESC")
            print("\nNode counts:")
            for record in result:
                print(f"  {record['label']}: {record['count']}")
            
            result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(*) as count ORDER BY count DESC")
            print("\nRelationship counts:")
            for record in result:
                print(f"  {record['type']}: {record['count']}")
        
        print("\n" + "="*60)
        print("Access Neo4j Browser at: http://localhost:7474")
        print("Username: neo4j")
        print("Password: admin2024")
        print("="*60)
        
    finally:
        driver.close()

if __name__ == "__main__":
    main()

