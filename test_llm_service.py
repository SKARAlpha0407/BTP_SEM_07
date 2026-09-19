import json
from backend.app.llm_service import call_llm

def test_llm_json_response():
    print("Testing llm_service.py for JSON response...")
    
    prompt = "Return a JSON object with a single key 'status' and value 'success'."
    response = call_llm(prompt, json_mode=True)
    
    print(f"LLM Response: {response}")
    
    try:
        parsed = json.loads(response)
        if parsed.get("status") == "success":
            print("SUCCESS: Received valid JSON with expected value.")
        else:
            print(f"FAILURE: JSON valid but unexpected content: {parsed}")
    except json.JSONDecodeError:
        print("FAILURE: Response is not valid JSON.")
        exit(1)

if __name__ == "__main__":
    test_llm_json_response()
