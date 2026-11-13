import re
from dataclasses import dataclass

class FormulaError(Exception):
    pass

def tokenize(text):
    # Matches parentheses and top-level atoms; comments begin with ';' and end at newline.
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == ';':
            j = text.find('\n', i)
            i = len(text) if j == -1 else j + 1
            continue
        if ch.isspace():
            i += 1
            continue
        if ch == '(' or ch == ')':
            tokens.append(ch)
            i += 1
            continue
        m = re.match(r'[^\s();]+', text[i:])
        if not m:
            raise FormulaError(f'unexpected character at offset {i}: {ch!r}')
        tokens.append(m.group(0))
        i += len(m.group(0))
    return tokens

def parse(text):
    tokens = tokenize(text)
    pos = 0

    def one():
        nonlocal pos
        if pos >= len(tokens):
            raise FormulaError('unexpected end of formula')
        tok = tokens[pos]
        pos += 1
        if tok == '(':
            items = []
            while pos < len(tokens) and tokens[pos] != ')':
                items.append(one())
            if pos >= len(tokens):
                raise FormulaError('missing closing parenthesis')
            pos += 1
            return items
        if tok == ')':
            raise FormulaError('unexpected closing parenthesis')
        return tok

    commands = []
    while pos < len(tokens):
        commands.append(one())
    return commands

@dataclass(frozen=True)
class Obligation:
    id: str
    commands: tuple
    expected_solver_result: str
    applies_to: str

def proof():
    # semantic AST for: exists x : 32-bit bit-vector such that x*256 != x<<8
    return Obligation('proof_xmul256_shl8', (
        ['set-logic', 'BV'],
        ['set-option', ':produce-models', 'true'],
        ['declare-const', 'x', ['_', 'BitVec', '32']],
        ['assert', ['not', ['=',
            ['bvmul', 'x', ['_', 'bv256', '32']],
            ['bvshl', 'x', ['_', 'bv8', '32']],
        ]]],
        ['check-sat'],
    ), 'unsat', 'formula-model-only')

def control25():
    return Obligation('counterexample_xmul256_vs_xmul25', (
        ['set-logic', 'BV'],
        ['set-option', ':produce-models', 'true'],
        ['declare-const', 'x', ['_', 'BitVec', '32']],
        ['assert', ['not', ['=',
            ['bvmul', 'x', ['_', 'bv256', '32']],
            ['bvmul', 'x', ['_', 'bv25', '32']],
        ]]],
        ['check-sat'],
        ['get-model'],
    ), 'sat', 'formula-model-only')

def controlleft7():
    return Obligation('counterexample_xmul256_vs_shl7', (
        ['set-logic', 'BV'],
        ['set-option', ':produce-models', 'true'],
        ['declare-const', 'x', ['_', 'BitVec', '32']],
        ['assert', ['not', ['=',
            ['bvmul', 'x', ['_', 'bv256', '32']],
            ['bvshl', 'x', ['_', 'bv7', '32']],
        ]]],
        ['check-sat'],
        ['get-model'],
    ), 'sat', 'formula-model-only')

OBLIGATIONS = {o.id: o for o in [proof(), control25(), controlleft7()]}

def inspect_formula(path):
    commands = parse(open(path, encoding='utf-8').read())
    for ob in OBLIGATIONS.values():
        if commands == list(ob.commands):
            return {
                'obligation_id': ob.id,
                'expected_solver_result': ob.expected_solver_result,
                'applies_to': ob.applies_to,
                'structure_errors': [],
            }
    # Return the closest mismatch for diagnostics without trusting the file.
    return {'obligation_id': None, 'expected_solver_result': None, 'applies_to': None,
            'structure_errors': ['formula AST does not match a declared obligation']}

def main():
    import sys, json
    for path in sys.argv[1:]:
        print(json.dumps(inspect_formula(path), sort_keys=True))

if __name__ == '__main__':
    main()
