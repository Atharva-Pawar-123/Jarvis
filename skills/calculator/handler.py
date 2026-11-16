import math

def execute(context: dict, params: dict) -> dict:
    expr = params.get("expression", "")
    if not expr:
        return {"result": "No expression provided."}
    
    # Safe eval environment
    allowed_names = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
        "pow": math.pow, "log": math.log, "abs": abs, "round": round
    }
    try:
        val = eval(expr, {"__builtins__": None}, allowed_names)
        return {"expression": expr, "result": val}
    except Exception as e:
        return {"error": f"Evaluation error: {e}"}
