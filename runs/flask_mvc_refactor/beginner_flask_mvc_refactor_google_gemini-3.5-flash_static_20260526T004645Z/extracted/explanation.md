An elegant way to refactor this Flask-style application is to separate the business logic (calculating user summaries and generating admin reports) from the routing/HTTP layer. This follows the MVC (Model-View-Controller) pattern, making the codebase much easier to maintain, test, and extend.

We will:
1. Create a new `services.py` file to house the core business logic.
2. Update `app.py` to import and use these service functions, keeping the route handlers thin and focused only on HTTP concerns (request handling and response formatting).
3. Update `test_app.py` to verify both the HTTP endpoints and the service functions directly.

Here are the complete contents of the refactored files:
