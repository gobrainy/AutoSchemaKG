"""
Quick test to validate OpenAI API key
"""
import os
from openai import OpenAI

# Test the API key from environment variable
api_key = os.getenv('OPENAI_API_KEY')  # Set your API key in environment variable

if not api_key:
    print("ERROR: OPENAI_API_KEY environment variable not set!")
    print("Please set it using: export OPENAI_API_KEY='your-key-here'")
    exit(1)

print("Testing OpenAI API key...")
print(f"Key: {api_key[:20]}...{api_key[-10:]}")
print("-" * 60)

try:
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.openai.com/v1"
    )
    
    # Make a simple test call
    print("Making test API call...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Say 'API key is valid!' in exactly 4 words."}
        ],
        max_tokens=20
    )
    
    result = response.choices[0].message.content
    print("\n" + "="*60)
    print("SUCCESS! API key is valid!")
    print("="*60)
    print(f"Response: {result}")
    print(f"Model used: {response.model}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print("\nYou can now run the full extraction script!")
    
except Exception as e:
    print("\n" + "="*60)
    print("FAILED! API key is NOT valid")
    print("="*60)
    print(f"Error: {e}")
    print("\nPlease check:")
    print("1. The API key is correct")
    print("2. You have remaining credits")
    print("3. The key has necessary permissions")

