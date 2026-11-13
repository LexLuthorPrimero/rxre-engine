#!/usr/bin/env python3
import sys, json

def select(question):
    q = question.lower()
    tools = []
    if any(k in q for k in ['entry','arch','cfg','symbolic','path']):
        tools.append('angr')
    if any(k in q for k in ['function','decompile','xref','reference','binary structure']):
        tools.append('ghidra')
    if any(k in q for k in ['explore','findings','bridge','structure']):
        tools.append('rea')
    if any(k in q for k in ['pack','unpack','patch','format','filesystem']):
        tools.append('ofrak')
    # evitar ejecutar todo por defecto
    if not tools:
        tools = ['ghidra']  # mínimo razonable
    return {'question': question, 'selected': tools, 'avoid_all': True}

if __name__=='__main__':
    print(json.dumps(select(sys.argv[1] if len(sys.argv)>1 else '¿entry point?'), indent=2))
