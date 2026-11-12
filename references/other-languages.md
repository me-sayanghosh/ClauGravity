# Multi-Language Bug Reference (Go, Java/Kotlin, C#, PHP, Ruby, Rust)

A concise, high-density audit checklist covering the top 10 recurring software defects, memory hazards, and security pitfalls across six major languages.

---

## 1. Go (Golang)

1. **Nil Map Assignment**
   - *Signal*: Writing to an uninitialized map variable (`var m map[string]int; m["key"] = 1`).
   - *Fix*: Initialize the map using `make(map[string]int)` prior to writing.
2. **Goroutine Leaks**
   - *Signal*: Spawning a goroutine that blocks indefinitely on an unbuffered channel or un-canceled context.
   - *Fix*: Pass `context.Context` and handle `<-ctx.Done()` or use bounded buffered channels.
3. **Loop Variable Capture in Closures**
   - *Signal*: Goroutine or closure capturing loop pointer variable directly across iterations (pre-Go 1.22).
   - *Fix*: Shadow the loop variable locally inside the loop block (`v := v`) or pass it as an explicit function argument.
4. **Ignored Errors via Blank Identifier**
   - *Signal*: Discarding error return values using blank identifier (`_, _ = io.Copy(...)`).
   - *Fix*: Check every error explicitly and return or wrap with descriptive context.
5. **Defer inside Long-Running Loops**
   - *Signal*: Calling `defer file.Close()` inside a loop over thousands of records, exhausting file descriptors.
   - *Fix*: Wrap loop body in an inline function or call `Close()` explicitly at iteration end.
6. **Data Races on Unsynchronized Shared Memory**
   - *Signal*: Modifying structs or maps across goroutines without `sync.Mutex` or atomic operations.
   - *Fix*: Protect shared memory with `sync.RWMutex` or pass data over typed channels.
7. **time.After Memory Leaks in Loops**
   - *Signal*: Calling `time.After()` in tight `select` loops, creating uncollected timers that leak memory.
   - *Fix*: Use a reusable `time.NewTimer()` and stop/reset it explicitly.
8. **Unsafe String-to-Byte Casting**
   - *Signal*: Using `unsafe.Pointer` to mutate byte slices converted from immutable strings.
   - *Fix*: Use standard copy conversion `[]byte(s)` or `strings.Builder`.
9. **Copying sync.Mutex Values**
   - *Signal*: Passing mutexes or structs containing mutexes by value rather than pointer.
   - *Fix*: Pass structs containing mutexes strictly by pointer reference (`*MyStruct`).
10. **Unclosed HTTP Response Body**
    - *Signal*: Calling `http.Get()` without `defer resp.Body.Close()`, leaking underlying TCP sockets.
    - *Fix*: Immediately follow successful HTTP requests with `defer resp.Body.Close()`.

---

## 2. Java and Kotlin

1. **NullPointerException (NPE)**
   - *Signal*: Dereferencing method return values without null checks or `Optional` wrapping.
   - *Fix*: Use `Objects.requireNonNull()`, `Optional<T>`, or Kotlin non-nullable types.
2. **Resource Leaks without Try-With-Resources**
   - *Signal*: Opening `InputStream`, `Connection`, or `Statement` in traditional try-catch without automatic closure.
   - *Fix*: Manage all `AutoCloseable` resources inside `try (...)` statements.
3. **equals() and hashCode() Contract Violation**
   - *Signal*: Overriding `equals()` without overriding `hashCode()`, causing `HashSet` and `HashMap` lookup failures.
   - *Fix*: Implement both methods consistently using IDE generators or Lombok `@EqualsAndHashCode`.
4. **SQL Injection via String Concatenation**
   - *Signal*: Building queries via `Statement.executeQuery("SELECT * FROM u WHERE id=" + id)`.
   - *Fix*: Use `PreparedStatement` with parameterized placeholders (`?`).
5. **Unsafe ObjectInputStream Deserialization**
   - *Signal*: Calling `readObject()` on arbitrary serialized streams from untrusted clients.
   - *Fix*: Use JSON/Protobuf serializers or apply strict `ValidatingObjectInputStream` filters.
6. **Silent Exception Swallowing**
   - *Signal*: Empty `catch (Exception e) {}` blocks in service methods.
   - *Fix*: Log exception details with stack trace and rethrow or return appropriate domain error.
7. **ConcurrentModificationException**
   - *Signal*: Modifying a collection while iterating through it without using `Iterator.remove()`.
   - *Fix*: Use `removeIf()` or concurrent collections (`CopyOnWriteArrayList`, `ConcurrentHashMap`).
8. **Thread Pool Exhaustion (CommonPool Starvation)**
   - *Signal*: Running blocking I/O calls inside parallel streams or `CompletableFuture.supplyAsync()` without custom executor.
   - *Fix*: Isolate blocking I/O to dedicated, bounded `ExecutorService` thread pools.
9. **SimpleDateFormat Thread-Safety Hazards**
   - *Signal*: Sharing static instances of `SimpleDateFormat` across concurrent threads.
   - *Fix*: Use thread-safe `java.time.format.DateTimeFormatter` (Java 8+).
10. **Kotlin Lateinit Access Before Initialization**
    - *Signal*: Reading a `lateinit var` before assignment, throwing `UninitializedPropertyAccessException`.
    - *Fix*: Guard with `::property.isInitialized` or use nullable types with default values.

---

## 3. C# (.NET)

1. **async void Methods**
   - *Signal*: Declaring asynchronous methods as `async void` instead of `async Task` (except event handlers).
   - *Fix*: Change return type to `async Task` so exceptions are observed and callers can await completion.
2. **Missing IDisposable Disposal**
   - *Signal*: Instantiating `SqlConnection`, `Stream`, or `HttpClient` without `using` declarations.
   - *Fix*: Utilize modern `using var resource = new Resource();` syntax.
3. **Null Dereferences with Nullable Contexts Disabled**
   - *Signal*: Unannotated reference types causing `NullReferenceException` in legacy assemblies.
   - *Fix*: Enable `<Nullable>enable</Nullable>` in `.csproj` and resolve compiler warnings.
4. **LINQ Multiple Enumeration Side Effects**
   - *Signal*: Iterating over an `IEnumerable<T>` returned from database queries multiple times.
   - *Fix*: Call `.ToList()` or `.ToArray()` to materialize results before repeated reads.
5. **Loop Variable Closure Pitfall**
   - *Signal*: Capturing loop variables in lambda expressions executed on another thread.
   - *Fix*: Create a local copy inside the loop or rely on C# 5+ foreach variable semantics.
6. **EF Core Client-Side Evaluation Traps**
   - *Signal*: Complex C# method invocations inside EF LINQ queries falling back to memory evaluation.
   - *Fix*: Keep query expressions translatable to SQL and inspect EF Core warning logs.
7. **Task.Result and Task.Wait Sync-over-Async Deadlocks**
   - *Signal*: Blocking on tasks with `.Result` or `.GetAwaiter().GetResult()` in UI or ASP.NET threads.
   - *Fix*: Refactor calling chain to asynchronous `await` end-to-end.
8. **BinaryFormatter Remote Code Execution**
   - *Signal*: Calling `BinaryFormatter.Deserialize()` on untrusted input streams.
   - *Fix*: Replace `BinaryFormatter` with `System.Text.Json` or contract-based serializers.
9. **HttpClient Socket Exhaustion**
   - *Signal*: Instantiating `new HttpClient()` per request rather than using `IHttpClientFactory`.
   - *Fix*: Inject `IHttpClientFactory` or manage single long-lived `HttpClient` instances.
10. **Non-Thread-Safe Generic Collection Mutation**
    - *Signal*: Writing to `List<T>` or `Dictionary<K, V>` concurrently across multiple tasks.
    - *Fix*: Use `ConcurrentDictionary<K, V>` or synchronize access with `lock`.

---

## 4. PHP

1. **Loose Type Juggling**
   - *Signal*: Evaluating comparisons with `==` instead of `===` (`"0e123" == "0e456"` evaluates to `true`).
   - *Fix*: Always enforce strict equality `===` and enable `declare(strict_types=1);`.
2. **Local and Remote File Inclusion (LFI/RFI)**
   - *Signal*: Passing `$_GET[page]` directly into `include` or `require`.
   - *Fix*: Validate requested files against a strict whitelist of known module names.
3. **SQL Injection via String Concatenation**
   - *Signal*: Concatenating variables into queries with `mysqli_query` or PDO `query()`.
   - *Fix*: Use PDO prepared statements with bounded parameters via `prepare()` and `execute()`.
4. **Insecure Deserialization via unserialize()**
   - *Signal*: Passing untrusted user strings into `unserialize()`, triggering object injection gadgets.
   - *Fix*: Use `json_decode()` or pass `allowed_classes => false` in `unserialize()`.
5. **Command Injection via Shell Functions**
   - *Signal*: Executing commands via `exec`, `system`, `passthru`, or backticks with user input.
   - *Fix*: Sanitize parameters with `escapeshellarg()` or use structured process libraries.
6. **HTTP Header / CRLF Injection**
   - *Signal*: Passing user data directly into `header("Location: " . $url)` without newline filtering.
   - *Fix*: Filter out `` and `
` characters or validate URLs before redirection.
7. **Missing CSRF Token Validation in Forms**
   - *Signal*: Processing `$_POST` actions without checking a session-stored CSRF token.
   - *Fix*: Enforce token validation on all state-altering requests using framework guards.
8. **Weak Password Hashing Algorithms**
   - *Signal*: Storing passwords hashed with `md5()` or `sha1()`.
   - *Fix*: Utilize `password_hash($pwd, PASSWORD_BCRYPT)` and verify with `password_verify()`.
9. **Variable Extraction via extract()**
   - *Signal*: Calling `extract($_GET)` or `extract($_POST)`, overwriting local variable state.
   - *Fix*: Avoid `extract()` and read specific keys directly from request superglobals.
10. **Memory Limit Exhaustion on Unbounded Uploads**
    - *Signal*: Loading entire uploaded files into memory buffers using `file_get_contents()`.
    - *Fix*: Stream large uploads using chunked streams and enforce `upload_max_filesize`.

---

## 5. Ruby

1. **Mass Assignment Vulnerability**
   - *Signal*: Passing raw params directly into `Model.create(params[:user])` without Strong Parameters.
   - *Fix*: Enforce `params.require(:user).permit(:name, :email)` in controllers.
2. **Arbitrary Code Execution via send() and eval()**
   - *Signal*: Calling `send(params[:method])` or `eval(params[:code])` with user input.
   - *Fix*: Whitelist permitted method names explicitly with `public_send()` and avoid `eval()`.
3. **ActiveRecord N+1 Query Traps**
   - *Signal*: Iterating over records and querying associations without `includes` or `joins`.
   - *Fix*: Eager-load associations with `Post.includes(:comments).all`.
4. **SQL Injection via String Interpolation in where()**
   - *Signal*: Calling `User.where("name = '#{params[:name]}'")`.
   - *Fix*: Use placeholder arrays: `User.where("name = ?", params[:name])` or hash conditions.
5. **Unsafe Deserialization via YAML.load**
   - *Signal*: Parsing YAML strings using `YAML.load` instead of `YAML.safe_load`.
   - *Fix*: Always use `YAML.safe_load` to prevent arbitrary Ruby object instantiation.
6. **CSRF Protection Disabled in Controllers**
   - *Signal*: Specifying `skip_before_action :verify_authenticity_token` on session-authenticated routes.
   - *Fix*: Maintain `protect_from_forgery with: :exception` and use token headers.
7. **Regex Anchor Confusion**
   - *Signal*: Using `^` and `$` for multiline matching when validating whole strings.
   - *Fix*: Use `\A` and `\z` to anchor validation to the absolute start and end of strings.
8. **XSS via raw() and html_safe**
   - *Signal*: Marking unsanitized user content as `raw(user_input)` or `user_input.html_safe`.
   - *Fix*: Allow Rails ERB auto-escaping or sanitize explicitly with `sanitize()`.
9. **Thread-Unsafe Class Variable Mutation**
   - *Signal*: Storing request-scoped state in class variables (`@@current_user`).
   - *Fix*: Use `CurrentAttributes` or thread-isolated storage (`Thread.current`).
10. **Missing Transactions in Multi-Step Callbacks**
    - *Signal*: Updating external associations in `after_save` callbacks without database transactions.
    - *Fix*: Wrap multi-model mutations in an explicit `ActiveRecord::Base.transaction` block.

---

## 6. Rust

1. **Production Panics via unwrap() and expect()**
   - *Signal*: Calling `.unwrap()` or `.expect()` in server request handlers on recoverable `Result`/`Option`.
   - *Fix*: Propagate errors using `?` operator or handle branches with `match` and `if let`.
2. **Unsoundness in unsafe Blocks**
   - *Signal*: Dereferencing raw pointers or violating aliasing rules without proving invariants.
   - *Fix*: Encapsulate `unsafe` in sound safe abstractions and run Miri to detect undefined behavior.
3. **Silent Integer Overflow in Release Builds**
   - *Signal*: Arithmetic operations on bounded integers that wrap silently under release optimization flags.
   - *Fix*: Use `checked_add()`, `saturating_add()`, or `overflowing_add()` for sensitive arithmetic.
4. **Unbounded Memory Allocation**
   - *Signal*: Reading network streams into `Vec<u8>` without a capacity ceiling (`read_to_end`).
   - *Fix*: Wrap readers in `.take(MAX_BYTES)` to enforce hard size limits.
5. **Deadlocks in Nested Mutex/RwLock Acquisitions**
   - *Signal*: Acquiring multiple `std::sync::Mutex` or `parking_lot::Mutex` locks in variable order.
   - *Fix*: Acquire locks in a globally deterministic order or combine related fields in a single lock.
6. **Blocking Async Runtimes with Synchronous Calls**
   - *Signal*: Executing blocking I/O or heavy compute inside Tokio async tasks without `spawn_blocking`.
   - *Fix*: Offload synchronous tasks using `tokio::task::spawn_blocking()`.
7. **Resource Leaks via Forgotten Channels**
   - *Signal*: Dropping channel receivers without notifying senders, causing send tasks to hang.
   - *Fix*: Monitor channel send outcomes and handle disconnection errors.
8. **Non-Monotonic Time Comparisons**
   - *Signal*: Measuring elapsed intervals with `SystemTime::now()` which can shift backwards on NTP adjustments.
   - *Fix*: Measure durations using `Instant::now()` which guarantees monotonic advancement.
9. **Infinite Loops in Iterators**
   - *Signal*: Calling `.cycle()` or creating open-ended range iterators without `.take()`.
   - *Fix*: Enforce explicit upper bounds on generator and adapter iterations.
10. **Forgotten Resource Drops on Abort**
    - *Signal*: Relying on `Drop` destructors when tasks can be canceled via `abort()`.
    - *Fix*: Structure cancellation using async teardown hooks or guarded cleanup structs.
