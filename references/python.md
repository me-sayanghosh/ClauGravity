# Python Code Audit and Pitfall Reference

A comprehensive guide to identifying defects, security flaws, and performance anti-patterns in Python applications, Django, Flask, and FastAPI frameworks.

---

## 1. Mutable Default Arguments
- **Signal**: Defining functions with mutable defaults such as `def fn(items=[])` or `def fn(data={})`.
- **Bad**:
  ```python
  def append_record(record, target_list=[]):
      target_list.append(record)
      return target_list # Mutates the same list across all calls!
  ```
- **Good**:
  ```python
  def append_record(record, target_list=None):
      if target_list is None:
          target_list = []
      target_list.append(record)
      return target_list
  ```

---

## 2. Late-Binding Closures in Loops
- **Signal**: Creating lambdas or functions inside a loop referencing the loop variable.
- **Bad**:
  ```python
  handlers = [lambda x: x + i for i in range(5)]
  # All functions return x + 4 because i is resolved at call time
  ```
- **Good**:
  ```python
  handlers = [lambda x, i=i: x + i for i in range(5)] # Default argument binds value eagerly
  ```

---

## 3. Bare Except and Overbroad Swallowing
- **Signal**: Catching `Exception` or using bare `except:` without logging or re-raising, silently swallowing `KeyboardInterrupt` or syntax issues.
- **Bad**:
  ```python
  try:
      execute_order(order)
  except:
      pass # Silently ignores critical failures and prevents Ctrl+C
  ```
- **Good**:
  ```python
  import logging
  try:
      execute_order(order)
  except PaymentGatewayError as err:
      logging.error("Payment failed for order %s: %s", order.id, err)
      raise
  ```

---

## 4. Float Equality Comparison
- **Signal**: Comparing floating-point numbers with `==` or `!=`.
- **Bad**:
  ```python
  total = 0.1 + 0.2
  if total == 0.3: # Evaluates to False due to IEEE 754 precision
      process()
  ```
- **Good**:
  ```python
  import math
  if math.isclose(total, 0.3, rel_tol=1e-9):
      process()
  ```

---

## 5. Unsafe Deserialization via pickle
- **Signal**: Calling `pickle.loads()` or `cPickle.loads()` on untrusted external data.
- **Bad**:
  ```python
  user_session = pickle.loads(request.raw_post_data) # Remote Code Execution
  ```
- **Good**:
  ```python
  import json
  user_session = json.loads(request.raw_post_data.decode("utf-8"))
  ```

---

## 6. Unsafe YAML Loading
- **Signal**: Calling `yaml.load(stream)` without specifying `Loader=yaml.SafeLoader` or using `yaml.safe_load(stream)`.
- **Bad**:
  ```python
  import yaml
  config = yaml.load(user_input_file) # Arbitrary Python object instantiation
  ```
- **Good**:
  ```python
  import yaml
  config = yaml.safe_load(user_input_file)
  ```

---

## 7. SQL f-Strings and String Formatting
- **Signal**: Interpolating variables into SQL strings using f-strings, `%`, or `.format()`.
- **Bad**:
  ```python
  cursor.execute(f"SELECT * FROM users WHERE email = '{user_email}'") # SQL Injection
  ```
- **Good**:
  ```python
  cursor.execute("SELECT * FROM users WHERE email = %s", (user_email,))
  ```

---

## 8. Subprocess Execution with shell=True
- **Signal**: Calling `subprocess.Popen`, `subprocess.run`, or `os.system` with `shell=True` and unquoted user input.
- **Bad**:
  ```python
  import subprocess
  subprocess.run(f"convert {user_filename} output.png", shell=True) # Command injection via ;
  ```
- **Good**:
  ```python
  import subprocess
  subprocess.run(["convert", user_filename, "output.png"], shell=False, check=True)
  ```

---

## 9. Blocking Calls in Asyncio Event Loops
- **Signal**: Calling synchronous I/O (`requests.get`, `time.sleep`, heavy CPU compute) inside `async def` functions without `run_in_executor`.
- **Bad**:
  ```python
  async def handle_request():
      time.sleep(2) # Blocks the entire single-threaded asyncio event loop
  ```
- **Good**:
  ```python
  import asyncio
  async def handle_request():
      await asyncio.sleep(2)
  ```

---

## 10. Django Raw Queries, DEBUG, ALLOWED_HOSTS, and CSRF Exemptions
- **Signal**: `DEBUG = True` in production, `ALLOWED_HOSTS = ["*"]`, using `Manager.raw()` with string formatting, or overbroad `@csrf_exempt`.
- **Bad**:
  ```python
  # settings.py
  DEBUG = True
  ALLOWED_HOSTS = ["*"]

  # views.py
  @csrf_exempt
  def sensitive_action(request):
      User.objects.raw(f"SELECT * FROM auth_user WHERE id = {request.GET[id]}")
  ```
- **Good**:
  ```python
  DEBUG = False
  ALLOWED_HOSTS = ["app.example.com"]

  def sensitive_action(request):
      User.objects.filter(id=request.GET["id"]).first()
  ```

---

## 11. Flask Debug Mode, Hardcoded Secrets, and Unsafe send_file
- **Signal**: Running `app.run(debug=True)` in production, hard-coded `app.secret_key = "secret"`, or using `send_file` with untrusted paths.
- **Bad**:
  ```python
  app.secret_key = "development-key"
  @app.route("/files/<path:filename>")
  def download(filename):
      return send_file(f"uploads/{filename}") # Path traversal
  ```
- **Good**:
  ```python
  import os
  from werkzeug.utils import secure_filename
  from flask import send_from_directory

  app.secret_key = os.environ["FLASK_SECRET_KEY"]
  @app.route("/files/<filename>")
  def download(filename):
      safe_name = secure_filename(filename)
      return send_from_directory("uploads", safe_name)
  ```

---

## 12. FastAPI Blocking Handlers and Data Leaks
- **Signal**: Defining `async def` endpoints that run blocking sync DB calls, or omitting `response_model` leading to password hash leakage.
- **Bad**:
  ```python
  @app.get("/users/{user_id}")
  async def get_user(user_id: int):
      user = sync_db_query(user_id) # Blocks worker loop; leaks password_hash
      return user
  ```
- **Good**:
  ```python
  from pydantic import BaseModel

  class UserOut(BaseModel):
      id: int
      username: str

  @app.get("/users/{user_id}", response_model=UserOut)
  def get_user(user_id: int): # Regular def runs in background threadpool
      return sync_db_query(user_id)
  ```

---

## 13. Missing Context Managers and Resource Leaks
- **Signal**: Opening files, database connections, or mutexes without a `with` statement.
- **Bad**:
  ```python
  f = open("log.txt", "w")
  f.write(data) # Leaks file descriptor if write raises IOError
  f.close()
  ```
- **Good**:
  ```python
  with open("log.txt", "w") as f:
      f.write(data)
  ```

---

## 14. Identity (is) vs. Equality (==) Confusion
- **Signal**: Using `is` to check equality for numbers, strings, or computed values.
- **Bad**:
  ```python
  a = 1000
  b = 1000
  if a is b: # Evaluates to False in CPython (outside small integer cache)
      proceed()
  ```
- **Good**:
  ```python
  if a == b:
      proceed()
  # Use `is` only for singletons like None, True, False:
  if val is None:
      pass
  ```

---

## 15. Naive vs. Aware Datetime Inconsistencies
- **Signal**: Comparing timezone-naive datetimes (`datetime.now()`) with timezone-aware datetimes (`datetime.now(timezone.utc)`).
- **Bad**:
  ```python
  from datetime import datetime, timezone
  now = datetime.now() # Naive local time
  expiry = datetime.now(timezone.utc) # Aware UTC
  if now > expiry: # Raises TypeError: can't compare offset-naive and offset-aware datetimes
      expire()
  ```
- **Good**:
  ```python
  from datetime import datetime, timezone
  now = datetime.now(timezone.utc)
  expiry = get_expiry_time()
  if now > expiry:
      expire()
  ```
