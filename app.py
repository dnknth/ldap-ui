from flask import Flask, jsonify, request, session
from ldap.schema.models import (Entry,
    AttributeType, ObjectClass,
    DITContentRule, DITStructureRule,
    MatchingRule, MatchingRuleUse,
    NameForm)

import ldap, sys


app = Flask( __name__)
app.config.from_object( 'settings')


# request.authorization --> {'username': 'dk', 'password': '***'}

@app.route( '/')
def index():
    return app.send_static_file( 'index.html')
