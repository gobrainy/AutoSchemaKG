"""
Import Knowledge Graph to Neo4j with MERGE (no duplicates)
This script handles incremental imports and deduplication
"""
import os
from neo4j import GraphDatabase
import pandas as pd

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "admin2024"

def import_nodes_with_merge(driver, csv_path, node_label):
    """Import nodes using MERGE to avoid duplicates"""
    print(f"\nImporting {node_label} nodes from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} nodes")
    
    with driver.session() as session:
        count = 0
        merged = 0
        created = 0
        
        for _, row in df.iterrows():
            # Determine ID column
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
            
            # MERGE instead of CREATE - avoids duplicates
            # Match on 'name' for entities/events, 'id' for concepts
            if label == 'Concept':
                match_key = 'id'
            else:
                match_key = 'name'
            
            query = f"""
            MERGE (n:{label} {{{match_key}: $match_value}})
            ON CREATE SET n = $props, n.created_count = 1
            ON MATCH SET n.created_count = coalesce(n.created_count, 0) + 1
            RETURN n.created_count as count
            """
            
            result = session.run(query, match_value=properties[match_key], props=properties)
            record = result.single()
            
            if record and record['count'] == 1:
                created += 1
            else:
                merged += 1
            
            count += 1
            
            if count % 100 == 0:
                print(f"  Processed {count} nodes (Created: {created}, Merged: {merged})...")
    
    print(f"Successfully processed {count} {node_label} nodes")
    print(f"  - Created new: {created}")
    print(f"  - Merged with existing: {merged}")

def import_text_nodes_with_merge(driver, csv_path, source_doc):
    """Import text nodes with source document tracking"""
    print(f"\nImporting text nodes from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} text nodes")
    
    with driver.session() as session:
        count = 0
        for _, row in df.iterrows():
            text_id = row['text_id:ID']
            original_text = row['original_text']
            
            # MERGE text nodes and add source tracking
            query = """
            MERGE (n:Text {id: $text_id})
            ON CREATE SET n.original_text = $original_text, n.sources = [$source_doc]
            ON MATCH SET n.sources = 
                CASE 
                    WHEN NOT $source_doc IN n.sources 
                    THEN n.sources + [$source_doc]
                    ELSE n.sources
                END
            """
            session.run(query, text_id=text_id, original_text=original_text, source_doc=source_doc)
            count += 1
    
    print(f"Successfully imported {count} text nodes")

def import_relationships_with_merge(driver, csv_path, rel_type, source_doc):
    """Import relationships, avoiding duplicates"""
    print(f"\nImporting {rel_type} relationships from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} relationships")
    
    with driver.session() as session:
        count = 0
        created = 0
        merged = 0
        
        for _, row in df.iterrows():
            start_id = row[':START_ID']
            end_id = row[':END_ID']
            
            properties = {'source_doc': source_doc}
            for col in df.columns:
                if col not in [':START_ID', ':END_ID', ':TYPE']:
                    val = row[col]
                    if pd.notna(val) and str(val) != '[]':
                        properties[col] = str(val)
            
            # Try to create relationship with MERGE
            try:
                # For Entity/Event nodes, match on 'name', for others on 'id'
                query = f"""
                MATCH (a) WHERE a.id = $start_id OR a.name = $start_id
                MATCH (b) WHERE b.id = $end_id OR b.name = $end_id
                MERGE (a)-[r:{rel_type} {{
                    relation: $relation,
                    source_doc: $source_doc
                }}]->(b)
                ON CREATE SET r = $props, r.created_count = 1
                ON MATCH SET r.created_count = coalesce(r.created_count, 0) + 1
                RETURN r.created_count as count
                """
                
                result = session.run(query, 
                                   start_id=start_id, 
                                   end_id=end_id, 
                                   relation=properties.get('relation', ''),
                                   source_doc=source_doc,
                                   props=properties)
                record = result.single()
                
                if record and record['count'] == 1:
                    created += 1
                else:
                    merged += 1
                
                count += 1
                
                if count % 100 == 0:
                    print(f"  Processed {count} relationships (Created: {created}, Merged: {merged})...")
            except Exception as e:
                # Skip if nodes don't exist
                pass
    
    print(f"Successfully processed {count} {rel_type} relationships")
    print(f"  - Created new: {created}")
    print(f"  - Merged with existing: {merged}")

def import_document_kg(data_dir, document_name, clear_first=False):
    """Import a single document's KG into Neo4j"""
    
    print("\n" + "="*60)
    print(f"Importing Knowledge Graph: {document_name}")
    print("="*60)
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        # Clear database only on first import if requested
        if clear_first:
            print("\nClearing existing data...")
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared!")
        
        # Import nodes
        triples_csv = os.path.join(data_dir, "triples_csv")
        
        # Import entity/event nodes
        nodes_pattern = f"triple_nodes_{document_name}_from_json_without_emb.csv"
        nodes_csv = os.path.join(triples_csv, nodes_pattern)
        if os.path.exists(nodes_csv):
            import_nodes_with_merge(driver, nodes_csv, "Node")
        else:
            print(f"Warning: {nodes_csv} not found")
        
        # Import text nodes
        text_pattern = f"text_nodes_{document_name}_from_json.csv"
        text_nodes_csv = os.path.join(triples_csv, text_pattern)
        if os.path.exists(text_nodes_csv):
            import_text_nodes_with_merge(driver, text_nodes_csv, document_name)
        else:
            print(f"Warning: {text_nodes_csv} not found")
        
        # Import relationships
        relations_pattern = f"triple_edges_{document_name}_from_json_without_emb.csv"
        relations_csv = os.path.join(triples_csv, relations_pattern)
        if os.path.exists(relations_csv):
            import_relationships_with_merge(driver, relations_csv, "RELATION", document_name)
        else:
            print(f"Warning: {relations_csv} not found")
        
        # Source relationships
        sources_pattern = f"text_edges_{document_name}_from_json.csv"
        sources_csv = os.path.join(triples_csv, sources_pattern)
        if os.path.exists(sources_csv):
            import_relationships_with_merge(driver, sources_csv, "SOURCE", document_name)
        else:
            print(f"Warning: {sources_csv} not found")
        
        # Import concept nodes
        concept_csv = os.path.join(data_dir, "concept_csv")
        
        concept_pattern = f"concept_nodes_{document_name}_from_json_with_concept.csv"
        concept_nodes_csv = os.path.join(concept_csv, concept_pattern)
        if os.path.exists(concept_nodes_csv):
            import_nodes_with_merge(driver, concept_nodes_csv, "Concept")
        else:
            print(f"Warning: {concept_nodes_csv} not found")
        
        # Concept relationships
        concept_edges_pattern = f"concept_edges_{document_name}_from_json_with_concept.csv"
        concept_edges_csv = os.path.join(concept_csv, concept_edges_pattern)
        if os.path.exists(concept_edges_csv):
            import_relationships_with_merge(driver, concept_edges_csv, "HAS_CONCEPT", document_name)
        else:
            print(f"Warning: {concept_edges_csv} not found")
        
        # Get statistics
        print("\n" + "="*60)
        print(f"Import Complete for: {document_name}")
        print("="*60)
        
        with driver.session() as session:
            result = session.run("""
                MATCH (n) 
                RETURN labels(n)[0] as label, count(*) as count 
                ORDER BY count DESC
            """)
            print("\nTotal Node counts:")
            for record in result:
                print(f"  {record['label']}: {record['count']}")
            
            result = session.run("""
                MATCH ()-[r]->() 
                RETURN type(r) as type, count(*) as count 
                ORDER BY count DESC
            """)
            print("\nTotal Relationship counts:")
            for record in result:
                print(f"  {record['type']}: {record['count']}")
        
    finally:
        driver.close()

def import_multiple_documents(document_configs, clear_first=True):
    """
    Import multiple documents with deduplication
    
    Args:
        document_configs: List of (data_dir, document_name) tuples
        clear_first: Whether to clear database before first import
    """
    
    for i, (data_dir, doc_name) in enumerate(document_configs):
        import_document_kg(data_dir, doc_name, clear_first=(clear_first and i == 0))
    
    print("\n" + "="*60)
    print("ALL DOCUMENTS IMPORTED!")
    print("="*60)
    print(f"\nAccess Neo4j Browser at: http://localhost:7474")
    print(f"Username: neo4j")
    print(f"Password: admin2024")

if __name__ == "__main__":
    # Import only graphmert document
    # Each tuple is (data_directory, document_name)
    
    documents = [
        ("import/graphmert", "graphmert.json"),
    ]
    
    import_multiple_documents(documents, clear_first=True)

