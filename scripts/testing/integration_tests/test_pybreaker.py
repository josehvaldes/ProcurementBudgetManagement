import pybreaker
import requests
import time


breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=8)

@breaker
def call_unreliable_service():
    print("Calling unreliable service...")
    response = requests.get("https://httpbin.org/status/500")
    if response.status_code != 200:
        print("Service failed with status code: {}".format(response.status_code))
        raise Exception("Service failed with status code: {}".format(response.status_code))
    
    print("Service succeeded with text: {}".format(response.text))
    return response.text

if __name__ == "__main__":
    for i in range(10):
        try:
            print("Attempting to call unreliable service...")
            result = call_unreliable_service()
            print("Service response:", result)
        except pybreaker.CircuitBreakerError:
            print("Circuit breaker is open. Skipping call.")
        except Exception as e:
            print("Error calling service:", e)
        time.sleep(2)