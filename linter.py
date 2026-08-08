import ast

class LookaheadLinter(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Call(self, node):
        # 1. Detect shift(-N), pct_change(-N), diff(-N) which leak future data
        if isinstance(node.func, ast.Attribute) and node.func.attr in ('shift', 'pct_change', 'diff'):
            for arg in node.args:
                if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    self.errors.append(f"Forbidden lookahead function call: {node.func.attr}(...) with negative offset")
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and arg.value < 0:
                    self.errors.append(f"Forbidden lookahead function call: {node.func.attr}(...) with negative offset")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        # 2. Detect forward indexing like index + 1 or index - -1
        sl = node.slice
        if isinstance(sl, ast.BinOp):
            if isinstance(sl.op, ast.Add):
                if isinstance(sl.right, ast.Constant) and isinstance(sl.right.value, int) and sl.right.value > 0:
                    self.errors.append(f"Forbidden forward index offset (addition) detected: index + {sl.right.value}")
            elif isinstance(sl.op, ast.Sub):
                if isinstance(sl.right, ast.UnaryOp) and isinstance(sl.right.op, ast.USub):
                    self.errors.append("Forbidden forward index offset (double negation) detected: index - negative value")
                elif isinstance(sl.right, ast.Constant) and isinstance(sl.right.value, int) and sl.right.value < 0:
                    self.errors.append(f"Forbidden forward index offset (subtraction of negative) detected: index - {sl.right.value}")
        self.generic_visit(node)

def verify_ast_lookahead(code: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"Failed to parse python code: {e}"
        
    linter = LookaheadLinter()
    linter.visit(tree)
    if linter.errors:
        return False, "; ".join(linter.errors)
    return True, ""
