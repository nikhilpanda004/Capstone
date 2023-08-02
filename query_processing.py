import pickle
import re
import pathlib
temp = pathlib.PosixPath
pathlib.PosixPath = pathlib.WindowsPath

query_templates = {
    'find_person': "MATCH (p:Person) WHERE p.name =~ '(?i){name}' RETURN p",
    'find_movie': "MATCH (m:Movie) WHERE m.title =~ '(?i){name}' RETURN m",
    'find_movie_by_relation': "MATCH q=(p:Person)-[r]->(m:Movie) WHERE type(r) in [{relationships}] and {where_clause} RETURN q",
    'find_all_movie_person': "Match q=(p:Person)-[]->(m:Movie) {where_clause} return q",
    'find_persons': "MATCH (p:Person) {where_clause} RETURN p",
    'find_movies': "MATCH (m:Movie) {where_clause} RETURN m",
    # 'shortest_path_between_two': "MATCH (({first_node}) {where_clause_1}), (({second_node}) {where_clause_2}), q = shortestPath(({first_node_nt})-[*..{hops}]-({second_node_nt})) RETURN q",
    'shortest_path_between_two': "MATCH ({first_node}), ({second_node}), q = shortestPath(({first_node_nt})-[*..{hops}]-({second_node_nt})) WHERE {where_clause_1} AND {where_clause_2} RETURN q",
    'shortest_path_from_node': "MATCH q = shortestPath({first_node}-[*..{hops}]-(p)) {where_clause} RETURN p",
    'hops_from_node': "MATCH x=({first_node})-[*1..{hops}]-(q) {where_clause} RETURN DISTINCT x"
}

def process_query(natural_text):
    # Load the NLP model from pickle file

    with open("./nlp_model.pkl" ,'rb') as f:
        nlp = pickle.load(f)
    
    # with open('model.pkl', 'rb') as f:
    #     model = pickle.load(f)

    # Process the natural text using the loaded NLP model
    #processed_text = recognize_entities(nlp, natural_text) #nlp.process(natural_text)

    # Generate the Cypher query based on the processed text
    cypher_query = generate_cypher_query(nlp, natural_text)

    return cypher_query

# Relationship Extraction
def relation_extraction(entities, verb_entities):
    entities_labels = [item[1] for item in entities]
    relationship_found = False
    if ('MOVIE' in entities_labels or 'WORK_OF_ART' in entities_labels) or 'PERSON' in entities_labels:
      if any(verb in verb_entities for verb in ['acted', 'act', 'perform', 'performed']):
        entities.append(('ACTED_IN', 'RELATIONSHIP'))
        relationship_found = True
      if any(verb in verb_entities for verb in ['follows', 'followed', 'monitored']):
        entities.append(('FOLLOWS', 'RELATIONSHIP'))
        relationship_found = True
      if any(verb in verb_entities for verb in ['directed', 'director', 'direction']):
        entities.append(('DIRECTED', 'RELATIONSHIP'))
        relationship_found = True
      if any(verb in verb_entities for verb in ['produced', 'made', 'bank rolled', 'rolled']):
        entities.append(('PRODUCED', 'RELATIONSHIP'))
        relationship_found = True
      if any(verb in verb_entities for verb in ['judged', 'review', 'reviewed']):
        entities.append(('REVIEWED', 'RELATIONSHIP'))
        relationship_found = True
      if any(verb in verb_entities for verb in ['written', 'wrote', 'author', 'authored']):
        entities.append(('WROTE', 'RELATIONSHIP'))
        relationship_found = True
    if not relationship_found and ('MOVIE' in entities_labels or 'WORK_OF_ART' in entities_labels) and 'PERSON' in entities_labels:
      entities.append(('ALL', 'RELATIONSHIP'))
    if relationship_found:
      if sum(1 for entity in entities if entity[1] == 'PERSON') == 0:
        entities.append(('', 'PERSON'))
      elif sum(1 for entity in entities if entity[1] == 'MOVIE') == 0 and sum(1 for entity in entities if entity[1] == 'WORK_OF_ART') == 0:
        entities.append(('', 'MOVIE'))
    return entities


def recognize_entities(nlp, text):
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        entities.append((ent.text, ent.label_))

    verb_entities = []
    for token in doc:
        if token.pos_ == "NOUN" and token.text.lower() in ["film", "movie", "films", "movies", "cinema", "cinemas"]:
          entities.append(("", "MOVIE"))
        elif token.pos_ == "NOUN" and token.text.lower() in ["actor", "actress", "star", "stars", "actors", "actresses", "people"]:
          entities.append(("", "PERSON"))
        elif token.pos_ == "NOUN" and token.text.lower() in ["hop", "hops", "step", "steps", "node", "nodes"]:
          entities.append(("", "HOPS"))
        elif token.pos_ == "ADJ" and token.text.lower() in ["closest", "close", "short", "shortest", "near", "nearest"]:
          entities.append(("", "PATH"))
        elif token.pos_ == "VERB":
          verb_entities.append(token.text.lower())
        if token.dep_ == "dobj" and token.head.lower_ in ["what", "where", "how"]:
            entities.append((token.text, "QUESTION_OBJECT"))
        if (token.dep_ == 'compound'):
          entities.append((token.text + ' ' + token.head.text , "NAME"))
    entities = relation_extraction(entities, verb_entities)
    if text.find("'") > -1 and text.rfind("'") < len(text):
      start_index = text.find("'") + 1
      end_index = text.rfind("'")
      attribute = text[start_index:end_index]
      entities.append((attribute, "ATTRIBUTE"))
    return entities

def generate_cypher_query(nlp, text):
  entities_mapping = {
      'WORK_OF_ART': 'Movie',
      'PERSON': 'Person',
      'MOVIE': 'Movie'
  }

  entities = recognize_entities(nlp, text)
  labels = [item[1] for item in entities]
  query_template = ''
  queries = []
  relations_template = ''
  limit_template = ''
  for entity in entities:
    (name, entity_label) = entity
    # SHORTEST PATH
    if entity_label == "PATH":
      where_clause_1 = ''
      where_clause_2 = ''
      first_node = ''
      second_node = ''
      first_node_nt = ''
      second_node_nt = ''

      hops = 10
      query_template = query_templates['shortest_path_between_two'] #'shortest_path_between_two': "MATCH (({first_node}) {where_clause_1}), (({second_node}) {where_clause_2}), q = shortestPath(({first_node_nt})-[*..{hops}]-({second_node_nt})) RETURN q",
      # First node
      for item, label in entities:
        if label == "PERSON" and item != '':
          first_node = "p1:Person"
          first_node_nt = 'p1'
          if where_clause_1 != '':
            where_clause_1 += " OR ANY(attribute IN keys(p1) WHERE p1[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_1 = "ANY(attribute IN keys(p1) WHERE p1[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break
        elif label == "MOVIE" and item != '':
          first_node = "m1:Movie"
          first_node_nt = 'm1'
          if where_clause_1 != '':
            where_clause_1 += " OR ANY(attribute IN keys(m1) WHERE m1[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_1 = "ANY(attribute IN keys(m1) WHERE m1[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break
        elif label == "WORK_OF_ART" and item != '':
          first_node = "m1:Movie"
          first_node_nt = 'm1'
          if where_clause_1 != '':
            where_clause_1 += " OR ANY(attribute IN keys(m1) WHERE m1[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_1 = "ANY(attribute IN keys(m1) WHERE m1[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break

      # Second node
      for item, label in entities:
        if label == "PERSON" and item != '':
          second_node = "p2:Person"
          second_node_nt = 'p2'
          if where_clause_2 != '':
            where_clause_2 += " OR ANY(attribute IN keys(p2) WHERE p2[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_2 = "ANY(attribute IN keys(p2) WHERE p2[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break
        elif label == "MOVIE" and item != '':
          second_node = "m2:Movie"
          second_node_nt = 'm2'
          if where_clause_2 != '':
            where_clause_2 += " OR ANY(attribute IN keys(m2) WHERE m2[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_2 = "ANY(attribute IN keys(m2) WHERE m2[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break
        elif label == "WORK_OF_ART" and item != '':
          second_node = "m2:Movie"
          second_node_nt = 'm2'
          if where_clause_2 != '':
            where_clause_2 += " OR ANY(attribute IN keys(m2) WHERE m2[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause_2 = "ANY(attribute IN keys(m2) WHERE m2[attribute] =~ '(?i)" + item + "')"
          entities.remove((item, label))
          break

      return query_template.replace('{first_node}', first_node).replace('{first_node_nt}', first_node_nt).replace('{second_node}', second_node).replace('{second_node_nt}', second_node_nt).replace('{where_clause_1}', where_clause_1).replace('{where_clause_2}', where_clause_2).replace('{hops}', str(hops))

    # HOPS
    if entity_label == "HOPS":
      where_clause = ''
      first_node = ''
      query_template = query_templates['hops_from_node']
      for item, label in entities:
        if label == "PERSON" and item != '':
          first_node = "p:Person"
          if where_clause != '':
            where_clause += " OR ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause = "WHERE ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
        elif label == "MOVIE" and item != '':
          first_node = "m:Movie"
          if where_clause != '':
            where_clause += " OR ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause = "WHERE ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
        elif label == "WORK_OF_ART" and item != '':
          first_node = "m:Movie"
          if where_clause != '':
            where_clause += " OR ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
          else:
            where_clause = "WHERE ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
        elif label == "CARDINAL" and re.match(r'^\d+$', item):
          query_template = query_template.replace('{hops}', item)
      return query_template.replace('{first_node}', first_node).replace('{where_clause}', where_clause)

    # PERSON
    if entity_label == 'PERSON' and sum(1 for entity in entities if entity[1] == 'RELATIONSHIP') == 0:
      if name != '':
        queries.append(query_templates['find_person'].replace('{name}', name))
      else:
        if sum(1 for entity in entities if entity[1] == 'NAME') == 0:
          where_clause = ''
          for item, label in entities:
            if label in ['ATTRIBUTE', 'GPE']:
              if where_clause != '':
                where_clause += ' OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
              else:
                where_clause += "WHERE ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')" + where_clause
            elif label in ['DATE']:
              if where_clause != '':
                where_clause += ' OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] = " + item + ")"
              else:
                where_clause += "WHERE ANY(attribute IN keys(p) WHERE p[attribute] = " + item + ")" + where_clause
          queries.append(query_templates['find_persons'].replace('{where_clause}', where_clause))
        else:
          for item, label in entities:
            if label == 'NAME':
              if name != '':
                queries.append(query_templates['find_person'].replace('{name}', item))
              elif sum(1 for entity in entities if entity[1] == 'PERSON') == 1:
                queries.append(query_templates['find_persons'])
              break
    # WORK OF ART
    elif entity_label == 'WORK_OF_ART' and sum(1 for entity in entities if entity[1] == 'RELATIONSHIP') == 0:
      queries.append(query_templates['find_movie'].replace('{name}', name))
    # MOVIE
    elif entity_label == 'MOVIE' and sum(1 for entity in entities if entity[1] == 'RELATIONSHIP') == 0:
      if sum(1 for entity in entities if entity[1] == 'NAME') == 0:
        where_clause = ''
        for item, label in entities:
          if label in ['ATTRIBUTE', 'GPE']:
            if where_clause != '':
              where_clause += ' OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
            else:
              where_clause += "WHERE ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')" + where_clause
          elif label in ['DATE']:
            if where_clause != '':
              where_clause += ' OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] = " + item + ")"
            else:
              where_clause += "WHERE ANY(attribute IN keys(m) WHERE m[attribute] = " + item + ")" + where_clause
        queries.append(query_templates['find_movies'].replace('{where_clause}', where_clause))
      else:
        for item, label in entities:
          if label == 'NAME':
            if name != '':
              queries.append(query_templates['find_movie'].replace('{name}', item))
            elif sum(1 for entity in entities if entity[1] in ['WORK_OF_ART', 'MOVIE']) == 1:
              queries.append(query_templates['find_movies'])
            break
    # RELATIONSHIP
    elif entity_label == 'RELATIONSHIP':
      if name == 'ALL':
        where_clause = ''
        for item, label in entities:
          if label == 'PERSON' and item != '':
            if where_clause != '':
              where_clause += 'OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
            else:
              where_clause += "WHERE ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
          elif label == 'WORK_OF_ART' and item != '':
            if where_clause != '':
              where_clause += 'OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
            else:
              where_clause += "WHERE ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
          elif label == "NAME" and item != '' and sum(1 for entity in entities if entity[1] == 'PERSON') == 1:
            if where_clause != '':
              where_clause += 'OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
            else:
              where_clause += "WHERE ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
          elif label == "NAME" and item != '' and sum(1 for entity in entities if entity[1] == 'MOVIE') == 1:
            if where_clause != '':
              where_clause += 'OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
            else:
              where_clause += "WHERE ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
        queries.append(query_templates['find_all_movie_person'].replace('{where_clause}', where_clause))
      else:
        if relations_template != '':
          relations_template += ", '" + name + "'"
        else:
          relations_template += "'" + name + "'"
    # CARDINAL
    elif entity_label == 'CARDINAL':
      limit_template = ' LIMIT ' + name

  # ALL RELATIONS
  if 'RELATIONSHIP' in labels and relations_template != '':
    where_clause = ''
    for item, label in entities:
      if label == 'PERSON' and item != '':
        if where_clause != '':
          where_clause += 'OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
        else:
          where_clause += " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
      elif label == 'WORK_OF_ART' and item != '':
        if where_clause != '':
          where_clause += 'OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
        else:
          where_clause += " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
      elif label == "NAME" and item != '' and sum(1 for entity in entities if entity[1] == 'PERSON') == 1:
        if where_clause != '':
          where_clause += 'OR ' + " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
        else:
          where_clause += " ANY(attribute IN keys(p) WHERE p[attribute] =~ '(?i)" + item + "')"
      elif label == "NAME" and item != '' and sum(1 for entity in entities if entity[1] == 'MOVIE') == 1:
        if where_clause != '':
          where_clause += 'OR ' + " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
        else:
          where_clause += " ANY(attribute IN keys(m) WHERE m[attribute] =~ '(?i)" + item + "')"
    queries.append(query_templates['find_movie_by_relation'].replace('{relationships}', relations_template).replace('{where_clause}', '(' + where_clause + ')'))

  for query in queries:
    if query_template != '':
      query_template += ' UNION ' + query + limit_template
    else:
      query_template += query + limit_template

  return query_template