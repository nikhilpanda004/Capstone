from flask import Flask, render_template, request, json
from flask_cors import CORS
import pickle
import os
from query_processing import process_query
#from app_copy import process_query

app = Flask(__name__)
CORS(app, support_credentials=True)

@app.route('/process_nlp', methods=['GET'])
def process_nlp():
    # Get the natural language query from the request
    query = request.args.get('query')

    # Process the query using query_processing module
    cypher_query =  process_query(query)

    # Execute the Cypher query and get the results
    # results = execute_cypher_query(cypher_query)

    # Return the processed query as a response
    response = {'processed_query': cypher_query}
    return app.response_class(response=json.dumps(response), mimetype='application/json')

if __name__ == '__main__':
    os.environ['KMP_DUPLICATE_LIB_OK']='True'
    app.run(debug=True, port=8000)