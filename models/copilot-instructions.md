# Project Coding Standards

## Python Standards
- Follow PEP 8 strictly
- Use type hints for all functions
- Minimum 80% test coverage required
- Use async/await for I/O operations
- Prefer FastAPI or Django for web frameworks
- Always use context managers for database connections

## JavaScript/TypeScript Standards
- ESLint strict mode enabled
- Use TypeScript for all new code
- Prefer functional components in React
- Follow Airbnb style guide
- Always handle errors explicitly

## Database Standards
- Always use transactions for multi-step operations
- Add appropriate indexes for all foreign keys
- Use parameterized queries (never string concatenation)
- Include rollback strategies in migrations
- Document schema changes in migration files

## Architecture Principles
- Follow microservices pattern where appropriate
- Event-driven architecture for async operations
- Repository pattern for data access layer
- Dependency injection for testability
- API-first design with OpenAPI specs

## Security Requirements
- Input validation on all user inputs
- Authentication required for all endpoints
- Rate limiting on public APIs
- Audit logging for sensitive operations
- Regular dependency updates

## Documentation
- All public APIs must have docstrings
- Architecture diagrams required for new features
- README updates for major changes
- API documentation auto-generated from code
