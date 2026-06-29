import ast
import json
import re


def _clean_single_value(val: str) -> str:
    val = val.strip()
    if val.startswith('"') and val.endswith('"') and len(val) >= 2:
        inner = val[1:-1]
        temp_token = "__ESCAPED_QUOTE_PLACEHOLDER__"
        inner_replaced = inner.replace('\\"', temp_token)
        inner_escaped = inner_replaced.replace('"', '\\"')
        inner_restored = inner_escaped.replace(temp_token, '\\"')
        return f'"{inner_restored}"'
    elif val.startswith('{') and val.endswith('}'):
        return _clean_json_values(val)
    return val


def _clean_json_values(s: str) -> str:
    s = s.strip()
    if not (s.startswith('{') and s.endswith('}')):
        return s

    key_pattern = re.compile(r'"([a-zA-Z0-9_]+)"\s*:\s*')
    matches = list(key_pattern.finditer(s))
    if not matches:
        return s
        
    chunks = []
    last_idx = 0
    
    for i in range(len(matches)):
        m = matches[i]
        start_key, end_key = m.span()
        
        chunks.append(s[last_idx:start_key])
        chunks.append(m.group(0))
        
        if i + 1 < len(matches):
            end_val = matches[i+1].start()
        else:
            end_val = len(s)
            while end_val > end_key and s[end_val-1] in ('}', ' ', '\t', '\n', '\r'):
                end_val -= 1
                
        val_str = s[end_key:end_val].strip()
        
        has_comma = False
        if val_str.endswith(','):
            val_str = val_str[:-1].strip()
            has_comma = True
            
        cleaned_val = _clean_single_value(val_str)
        chunks.append(cleaned_val)
        if has_comma:
            chunks.append(",")
            
        last_idx = end_val
        if i + 1 == len(matches):
            chunks.append(s[end_val:])
            
    return "".join(chunks)


def robust_json_parse(s: str) -> dict:
    """
    Attempts to parse a string into a JSON dictionary, using multiple fallback
    strategies to handle common LLM output formatting errors.
    """
    s = s.strip()
    
    try:
        return json.loads(s, strict=False)
    except Exception as e:
        last_err = e

    # Fallback 1: Extract JSON from markdown or preamble
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if match:
        candidate = match.group()
        try:
            return json.loads(candidate, strict=False)
        except Exception as e:
            last_err = e
            s = candidate

    # Fallback 2: Try to escape unescaped inner quotes
    try:
        escaped = _clean_json_values(s)
        return json.loads(escaped, strict=False)
    except Exception as e:
        last_err = e

    # Fallback 3: Try ast.literal_eval if it's Python dict syntax
    try:
        cleaned = s.replace("true", "True").replace("false", "False").replace("null", "None")
        res = ast.literal_eval(cleaned)
        if isinstance(res, dict):
            return res
    except Exception as e:
        last_err = e

    raise last_err
