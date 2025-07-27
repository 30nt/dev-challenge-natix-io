# API Breaking Changes - My Answers

Based on my understanding of API management and the weather service project I've built as a demonstration ([see README.md](weather-service/README.md)).

## 1. What Is a Breaking Change?

A breaking change is any modification to the API that would cause existing frontend clients to fail or behave incorrectly without code changes on their side. In my view, here are the most potentially problematic breaking changes:

**Example 1: Field Name Changes**
Changing `"Weather"` to `"weather"` (case sensitivity) or renaming it to `"forecast"`. This could potentially break React apps where they do `response.Weather.map()` - suddenly they might get "cannot read property 'map' of undefined". Case sensitivity issues are particularly tricky because they might work in some environments but fail in others.

**Example 2: Data Type Changes**
Changing `"temperature": "18"` (string) to `"temperature": 18` (number). Frontend code that does string operations like `temperature + "°C"` would theoretically break and display "18°C" as "NaN°C". Type coercion in JavaScript can mask these issues until they hit edge cases.

**Example 3: Field Removal**
Removing any existing field. For example, removing the `"condition"` field entirely. Any frontend code referencing `item.condition` would potentially crash with undefined errors. This is particularly problematic because it's not immediately obvious during testing - you might only discover it when you encounter specific weather conditions.

## 2. Coordinating Across Multiple Frontends

I should note that I don't have production experience maintaining multiple backend API versions simultaneously. My approach is based on theoretical knowledge and best practices I've researched. However, I've implemented some of these strategies in my demo project to showcase my understanding:

**API Versioning Strategy**
My approach would be to implement what I demonstrated in this weather service project - multiple API versions running simultaneously. Keep `/v1/weather` exactly as it is, introduce `/v2/weather` with the new schema. This theoretically gives frontend teams time to migrate at their own pace. In my demo, you can see this dual-version approach with consistent error handling between versions.

**Deprecation Timeline**
I believe in giving slow-updating clients at least 6 months notice. Add deprecation headers to v1 responses (`X-API-Deprecated: true`, `X-Deprecation-Date: 2025-12-31`) like I implemented in my project. This should give teams clear visibility into what's coming, especially for teams that only update quarterly.

**Communication Strategy**
In theory, I'd create a detailed migration guide with before/after examples and timeline. Based on what I've read about API management, just sending notifications isn't enough - you need proactive communication with each frontend team.

## 3. How to Catch Breaking Changes During Development

This is where tooling and process really matter. Here's my approach based on best practices I've studied:

**Schema Validation Testing**
My recommendation would be to implement automated tests that validate the exact JSON response structure against the published contract. In this weather project, I have comprehensive tests checking response schemas. Any change that breaks the contract should fail CI immediately. This approach would catch structural changes before they reach production.

**Contract Testing**
I'd suggest using tools like Pact or JSON Schema validation in your test suite. Each API endpoint should have a contract test that verifies the exact structure, field types, and required fields. In my demo project, I use Pydantic models which automatically validate response structure - any breaking change would cause test failures.

**Pre-Production Validation**
My advice would be to run the new API version against real frontend code in a staging environment before any release. This approach should catch breaking changes that pass unit tests but fail with actual frontend implementations. The key would be using real frontend builds, not just API testing tools.

**Code Review Checklists**
I believe in establishing clear review guidelines: any change to response models should require explicit approval and frontend team notification. My view is that any change to public-facing schemas needs careful consideration and stakeholder sign-off.

## 4. Policy for Releasing Changes

While I haven't worked in a team environment with established API change policies, here's what I think would be an effective approach based on industry best practices:

**Semantic Versioning for APIs**
I'd recommend adopting semantic versioning not just for code, but for API contracts. Minor version bumps for additive changes (new optional fields), major version bumps for breaking changes. This should give frontend teams a clear signal about the impact of changes.

**Change Categories & Approval Process**
My suggested approach would be:
- **Safe changes** (adding optional fields): Normal code review process
- **Potentially breaking changes** (changing field types, making fields required): Required stakeholder review and explicit approval
- **Breaking changes** (removing fields, changing response structure): Required architecture review, migration plan, and deprecation period

**Documentation-First Approach**
I believe in updating API documentation before implementing any change. This should force developers to think through the impact and communicate changes clearly. Using OpenAPI specs (like I do in this weather project with Swagger/ReDoc) as the source of truth would be my recommended approach.

**Gradual Rollout Strategy**
For major changes, my recommendation would be to roll out the new version to a small percentage of traffic first, monitor for errors, then gradually increase. Having monitoring specifically for 4xx/5xx error rates per API version should help catch integration issues early.

My key insight is that most API breaking changes probably aren't intentional - they likely happen because developers don't realize the downstream impact. Having clear processes and tooling to catch these automatically would be way more effective than relying on people to remember to check.