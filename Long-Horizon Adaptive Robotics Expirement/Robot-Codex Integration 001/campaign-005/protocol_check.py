"""Validate the small draft-07 subset used by the pinned RPC schemas.

Unknown validation keywords fail closed. This is not a general JSON Schema API.
"""
def validate(value,schema,root=None):
    if schema is True:return
    if schema is False:raise AssertionError('False schema')
    root=schema if root is None else root
    annotation={'$schema','title','description','definitions','default'}
    supported=annotation|{'$ref','type','properties','required','items','enum','anyOf','oneOf','additionalProperties'}
    assert set(schema)<=supported,'Unsupported schema keyword '+str(set(schema)-supported)
    if '$ref' in schema:
        assert schema['$ref'].startswith('#/')
        target=root
        for part in schema['$ref'][2:].split('/'):target=target[part]
        validate(value,target,root);return
    for key in ('anyOf','oneOf'):
        if key in schema:
            matches=0
            for branch in schema[key]:
                try:validate(value,branch,root);matches+=1
                except AssertionError:pass
            assert matches>=1 if key=='anyOf' else matches==1
    if 'enum' in schema:assert value in schema['enum']
    types={'object':dict,'array':list,'string':str,'boolean':bool,'integer':int,'number':(int,float),'null':type(None)}
    if 'type' in schema:
        options=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        assert any(isinstance(value,types[t]) and (t not in ('integer','number') or type(value) is not bool) for t in options)
    if isinstance(value,dict):
        assert set(schema.get('required',[]))<=set(value)
        for k,v in value.items():
            if k in schema.get('properties',{}):validate(v,schema['properties'][k],root)
            elif schema.get('additionalProperties') is False:raise AssertionError('Extra field '+k)
    if isinstance(value,list) and 'items' in schema:
        for item in value:validate(item,schema['items'],root)
