# TRIPRESCUE — COMPLETE MASTER DEVELOPMENT SPECIFICATION

## 1. PROJECT OVERVIEW

**Project Name:** TripRescue

**Tagline:** Your Trip. Your People. Your AI Buddy.

**Project Type:** Full-stack, AI-powered travel planning, group coordination, and disruption recovery web application.

**Purpose:** Build an intelligent travel companion that helps people plan vacations, manage itineraries, discover spontaneous adventures, coordinate group activities, and recover from travel disruptions.

TripRescue should feel like having a knowledgeable, friendly travel companion who understands the traveler, remembers preferences, helps make decisions, and can take approved actions inside the application.

This is a university hackathon project. The final product must be visually impressive, technically functional, and demonstrate meaningful AI capabilities.

**Most important principle: Build a working product, not a collection of static UI mockups.**

The application must have six fully integrated features:

1. Dream-to-Trip — AI Trip Planning
2. Travel Buddy with Memory
3. Domino Rescue — Automatic Trip Repair
4. SideQuest — Spontaneous Adventures
5. Group Harmony — AI Group Travel Negotiator
6. SplitQuest — Smart Group Splitting

These features must share the same user accounts, trip records, itinerary data, preferences, group information, and AI assistant.

---

# 2. EXISTING PROJECT — CRITICAL INSTRUCTIONS

This project already exists and has been partially implemented.

The existing stack includes:

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Python
- FastAPI
- SQLAlchemy
- SQLite

The existing FastAPI backend previously passed six tests, and its interactive documentation was accessible at `http://localhost:8000/docs`.

However, do not assume the current codebase still has exactly the same structure or functionality.

**Before modifying anything:**

1. Read the existing `PROJECT_SPEC.md` and relevant project files.
2. Inspect the actual frontend and backend directory structures.
3. Identify all existing models, database tables, API routes, services, and tests.
4. Identify which features are already implemented and which are incomplete.
5. Preserve existing working functionality.
6. Do not delete the database or existing trip records.
7. Do not overwrite working code unnecessarily.
8. Avoid destructive schema changes.
9. Use database migrations when appropriate.
10. Update existing components rather than rebuilding the project from scratch.

If a dependency, API key, or provider configuration is missing, explain what is required and provide a safe fallback.

Never claim a feature works unless it has been implemented and tested.

---

# 3. PRODUCT EXPERIENCE

## Main Vision

TripRescue should not feel like a traditional travel booking website.

It should feel like an intelligent travel workspace centered around an AI companion.

Users should be able to communicate naturally:

"Plan a peaceful mountain vacation under $800."

"Remember that I don't like crowded places."

"We're traveling with four people, and everyone wants something different."

"We have two hours before dinner. Find something fun."

"Two of us want shopping, and the others want museums."

"My flight was canceled. What happens to the rest of my trip?"

The AI should understand these requests, use available application data, generate structured proposals, and perform approved actions.

## Primary User Journey

1. User opens TripRescue.
2. User creates or selects a traveler profile.
3. User chats with their AI Travel Buddy.
4. The buddy helps plan a trip.
5. User reviews the generated itinerary.
6. User saves the trip.
7. User can invite or add group members.
8. Group Harmony coordinates preferences.
9. SideQuest generates spontaneous adventures.
10. SplitQuest creates temporary subgroup itineraries.
11. The buddy remembers preferences and trip history.
12. If a disruption occurs, Domino Rescue identifies consequences and proposes recovery options.
13. User approves changes.
14. The application updates persistent trip records and shows the result.

The user should never have to re-enter information that is already saved and relevant.

---

# 4. FEATURE 1 — DREAM-TO-TRIP

## Goal

Allow users to describe their dream vacation in natural language and receive a personalized, realistic, editable itinerary.

## Example

User:

"I want a seven-day vacation somewhere with mountains and lakes. My budget is $1,200. I love photography, hiking, and peaceful places."

The AI should:

1. Extract the user's travel preferences.
2. Ask for essential missing information, such as departure city or travel dates, when necessary.
3. Suggest suitable destinations.
4. Explain why each destination matches the request.
5. Generate a day-by-day itinerary after the user selects a destination.
6. Estimate costs.
7. Consider travel time, geographic proximity, activity duration, and opening hours when reliable data is available.
8. Save the itinerary to the database after approval.

## Required Inputs

- Departure location
- Destination or desired type of destination
- Travel dates
- Number of travelers
- Total or per-person budget
- Interests
- Travel pace
- Accommodation preferences
- Transportation preferences
- Accessibility or mobility needs, when provided
- Food preferences or dietary restrictions, when provided

Do not require every optional field before generating a draft.

## Required Outputs

A structured trip containing:

- Trip name
- Destination
- Start and end dates
- Travelers
- Budget
- Day-by-day schedule
- Activities
- Estimated activity durations
- Locations
- Transportation suggestions
- Estimated costs
- Notes and explanations

## Itinerary Functionality

Users must be able to:

- Save generated trips.
- View saved trips.
- Edit trip details.
- Add activities.
- Remove activities.
- Reschedule activities.
- Reorder itinerary items.
- Regenerate a day.
- Regenerate an individual activity.
- Ask the buddy to modify the itinerary.
- See estimated budget changes.
- Review changes before saving them.

## Technical Requirements

AI output must use validated structured JSON rather than unstructured paragraphs alone.

Use Pydantic models to validate itinerary proposals.

Separate AI-generated recommendations from confirmed reservations.

Do not present invented prices, opening hours, or availability as verified facts.

When reliable live data is unavailable, display estimates clearly.

---

# 5. FEATURE 2 — TRAVEL BUDDY WITH MEMORY

## Goal

Build a conversational AI companion that remembers relevant user preferences and understands the current trip.

The AI buddy should be the central interaction point of the application.

## Personality

The buddy should feel:

- Friendly
- Helpful
- Conversational
- Supportive
- Knowledgeable
- Adaptable to the user's preferred communication style

It should avoid sounding robotic or excessively formal.

The user should be able to choose a communication style such as:

- Friendly and casual
- Professional
- Enthusiastic
- Concise

Personality must never override factual accuracy or safety.

## Memory System

The buddy should maintain structured, persistent information such as:

- Preferred travel pace
- Favorite activities
- Disliked activities
- Food preferences
- Typical budget range
- Preferred destinations
- Accommodation preferences
- Transportation preferences
- Explicitly saved travel interests

Memory must be associated with the correct user.

## Example

User:

"I don't really enjoy crowded tourist attractions."

The buddy:

"Got it. I'll prioritize quieter experiences when planning your trips."

On a future trip, the buddy should use this saved preference when making recommendations.

## Memory Requirements

Implement at least three levels of context:

### User Profile Memory

Long-term preferences that may apply across multiple trips.

### Trip Memory

Information specific to the current trip, such as budget, travelers, destination, and planned activities.

### Conversation Context

Recent chat messages and relevant conversation history.

The buddy should retrieve relevant context before responding.

## Memory Controls

Users must be able to:

- View saved preferences.
- Add preferences.
- Edit preferences.
- Delete preferences.
- Decide whether a preference should be remembered.

Do not silently store sensitive personal information.

Avoid exposing one user's memories to another user.

## AI Tools

The buddy should be able to invoke backend functions such as:

- Get current trip
- Get itinerary
- Search saved preferences
- Save a preference
- Propose itinerary changes
- Add approved activities
- Remove approved activities
- Check budget
- Generate SideQuest
- Generate Group Harmony plan
- Generate SplitQuest
- Analyze disruption
- Generate recovery options

**Important:** The AI should not directly modify database records without using validated backend services.

## Action Approval

For changes that modify trip plans, bookings, or shared group data:

1. AI generates a proposal.
2. Frontend displays the proposed changes.
3. User reviews the changes.
4. User approves or rejects.
5. Backend executes the approved action.
6. Database records the result.
7. UI refreshes with updated information.

The buddy should never claim an action succeeded before receiving confirmation from the backend.

---

# 6. FEATURE 3 — DOMINO RESCUE

## Goal

Automatically identify how one travel disruption affects the rest of a trip and generate coordinated recovery plans.

This is one of TripRescue's most important technical differentiators.

## Example

A traveler has:

- Flight from Columbus to Chicago
- Connecting flight from Chicago to Tokyo
- Hotel reservation in Tokyo
- Airport pickup
- Guided tour the following morning

The connecting flight gets canceled.

TripRescue should identify the cancellation and determine which downstream plans are affected.

## Dependency Graph

Represent itinerary relationships as a directed dependency graph.

Example:

Flight Arrival → Airport Pickup → Hotel Check-in → Next-Day Tour

The dependency graph should support:

- Nodes representing reservations or itinerary events
- Edges representing scheduling or logistical dependencies
- Affected reservation detection
- Conflict identification
- Recovery impact analysis

A canceled or delayed flight should trigger analysis of dependent reservations.

## Disruption Types

Support at least:

- Flight cancellation
- Flight delay
- Missed connection
- Hotel cancellation
- Activity cancellation

For the hackathon, flight cancellation is the required fully working demonstration.

## Recovery Engine

Generate recovery options using available alternatives.

Rank options according to:

- Estimated total cost
- Arrival time
- Number of changes required
- Number of affected reservations
- User preferences
- Overall disruption severity

Provide at least three strategies when valid alternatives exist:

- Fastest recovery
- Cheapest recovery
- Balanced recovery

Do not fabricate multiple distinct alternatives when the data does not support them.

## Recovery Workflow

1. Disruption is detected or simulated.
2. Backend updates disruption status.
3. Dependency graph is analyzed.
4. Affected itinerary items are identified.
5. Recovery options are generated.
6. User sees a comparison.
7. User approves a recovery option.
8. Backend executes supported or simulated changes.
9. Database records new reservation states.
10. The itinerary and activity log update.

## Mock Provider Support

Real travel booking integrations may not be available.

Implement clearly labeled mock booking adapters that simulate:

- Searching alternative flights
- Changing flight reservations
- Updating airport pickup
- Rescheduling activities
- Canceling eligible mock reservations

Mock execution must produce real, persisted state changes inside TripRescue.

Never imply that a simulated action modified a real-world reservation.

## Audit Trail

Store:

- Disruption event
- Affected reservations
- Proposed recovery plan
- User approval
- Executed actions
- Execution status
- Failures, if any
- Timestamps

Include protection against duplicate execution.

If a mock action fails, the system must show the failure rather than claiming the trip was fully repaired.

---

# 7. FEATURE 4 — SIDEQUEST

## Goal

Generate spontaneous mini-adventures when travelers have free time.

## Example

User:

"We have 90 minutes before dinner. Find something interesting nearby for under $30."

The buddy should:

1. Identify the user's current or selected location.
2. Determine available time.
3. Check the existing itinerary for conflicts.
4. Consider the user's interests.
5. Consider the spending limit.
6. Find suitable activities.
7. Arrange them in a practical order.
8. Estimate travel time.
9. Generate a mini-itinerary.
10. Offer to save it to the main trip.

## Inputs

- Current or manually selected location
- Available time
- Spending limit
- Interests
- Group size
- Transportation mode
- Existing schedule

## Outputs

A SideQuest containing:

- Title
- Theme
- Recommended stops
- Stop descriptions
- Estimated duration
- Estimated travel time
- Estimated cost
- Proposed route
- Start and end times

## Required Functionality

Users should be able to:

- Generate a SideQuest.
- Regenerate a SideQuest.
- Change its theme.
- Change time available.
- Change budget.
- Review proposed stops.
- Save it to the itinerary.
- Reject it without changing the itinerary.

## Location Handling

Request location permission only when needed.

Support manual location entry if permission is unavailable or denied.

If a map or places API is unavailable, use clearly labeled curated demonstration locations with known coordinates.

Do not fabricate precise travel times or business opening hours.

---

# 8. FEATURE 5 — GROUP HARMONY

## Goal

Create group trips that balance the interests and constraints of multiple travelers.

## Example

Three friends are traveling to Japan.

Traveler A:
- Loves nature
- Budget: $1,200
- Prefers relaxing activities

Traveler B:
- Loves anime and shopping
- Budget: $1,800
- Prefers busy itineraries

Traveler C:
- Loves food and culture
- Budget: $1,500
- Prefers moderate activity

The system should generate a balanced itinerary.

## Group Management

Users should be able to:

- Create a travel group.
- Add members to the group.
- Edit member preferences.
- Set individual budgets.
- Assign group roles.
- View group preferences.
- Generate a group itinerary.
- Review the proposed compromise.

For the hackathon, manually adding fictional group members is acceptable.

Real invitation and authentication systems can be added later.

## Preference Scoring

Implement an explainable scoring system.

Possible factors:

- Interest match
- Budget compatibility
- Travel pace compatibility
- Accessibility constraints
- Time availability
- Group fairness

The scoring system should avoid consistently prioritizing one traveler.

## Output

Display:

- Proposed shared itinerary
- Which travelers benefit from each activity
- Budget implications
- Preference match scores
- Reasons for compromises
- Unresolved conflicts

## Approval

The organizer should be able to approve or reject the generated group itinerary.

For the MVP, the organizer may approve on behalf of simulated group members.

Clearly distinguish simulated participants from real authenticated users.

---

# 9. FEATURE 6 — SPLITQUEST

## Goal

Allow a group to temporarily split into smaller groups with different activities and then reunite.

This feature should integrate with Group Harmony.

## Example

Four friends are traveling together.

Two want to shop.

Two want to visit museums.

The buddy should generate:

Group A:
- Shopping itinerary
- Relevant locations
- Estimated travel time
- Estimated spending

Group B:
- Museum itinerary
- Relevant locations
- Estimated travel time
- Estimated spending

Both groups should reunite at a practical meeting location and time.

## Required Inputs

- Group members
- Subgroup assignments
- Interests
- Available time
- Current location
- Spending limits
- Transportation preferences
- Desired reunion time

## Required Outputs

- Subgroup A itinerary
- Subgroup B itinerary
- Estimated duration
- Travel times
- Individual or subgroup costs
- Shared meeting point
- Meeting time
- Explanation of why the meeting point was selected

## Technical Requirements

Use schedule constraints to prevent conflicts.

The reunion point should be reachable from both subgroup routes within the available time.

If travel times cannot be verified, label them as estimates.

The buddy should identify infeasible plans instead of inventing a workable route.

## Required Functionality

Users should be able to:

- Select members for each subgroup.
- Generate subgroup itineraries.
- Compare routes.
- Change reunion time.
- Regenerate either subgroup plan.
- Approve the combined SplitQuest.
- Save subgroup activities to the shared trip.

Group members' activities should remain distinguishable in the itinerary.

---

# 10. APPLICATION DESIGN

## Design Direction

Create a premium, modern, visually polished travel application.

It should feel like a real consumer product, not a university assignment or generic admin dashboard.

Design inspiration:

- Modern travel applications
- Premium AI productivity tools
- Clean map-based interfaces
- Conversational AI products
- Editorial travel photography

## Visual Style

Use:

- Spacious layouts
- Rounded cards
- Clear typography
- High-quality destination photography
- Subtle shadows
- Smooth transitions
- Consistent icons
- Thoughtful empty states
- Accessible color contrast
- Responsive layouts

Avoid:

- Excessive gradients
- Unnecessary animations
- Crowded dashboards
- Generic placeholder cards
- Dead buttons
- Fake loading screens
- Inconsistent spacing
- Hardcoded user trips disguised as live data

## Main Navigation

Implement:

1. Dashboard
2. My Trips
3. AI Travel Buddy
4. Explore / SideQuest
5. Groups
6. Trip Details
7. Preferences / Settings

Domino Rescue should be accessible through the relevant trip and its disruption alerts.

## Dashboard

Show:

- Upcoming trips
- Current active trip
- Next scheduled activity
- AI Buddy entry point
- Recent trip updates
- Travel alerts
- Quick actions

## Trip Details Page

Include:

- Destination hero image
- Trip dates
- Travelers
- Budget summary
- Chronological itinerary
- Activity cards
- Reservations
- Group information
- AI Buddy panel
- Recovery status

## AI Buddy Interface

The chat should support:

- User messages
- AI responses
- Structured itinerary cards
- Trip suggestions
- Proposed changes
- Approval controls
- Loading states
- Error states
- Conversation history

Where useful, allow users to open the buddy in a side panel while viewing the itinerary.

## Maps

Use an appropriate map provider or open-source map solution.

Show:

- Activity markers
- Routes
- SideQuest stops
- SplitQuest subgroup routes
- Reunion point

If routing data is unavailable, do not draw misleading travel routes.

## Responsive Design

The application must work on:

- Desktop
- Laptop
- Tablet
- Mobile

Mobile navigation and chat usability are especially important.

---

# 11. TECHNICAL ARCHITECTURE

## Frontend

Use the existing React + TypeScript + Vite application.

Preferred libraries:

- Tailwind CSS
- shadcn/ui
- Lucide icons
- React Router
- TanStack Query for server state
- React Hook Form and Zod for validated forms

Only add dependencies that are justified and compatible with the existing project.

## Backend

Use the existing Python FastAPI application.

Preferred components:

- FastAPI
- SQLAlchemy
- Pydantic
- SQLite for local development
- Alembic for database migrations
- Pytest for backend testing

## AI Integration

Use an AI provider through the backend, with OpenAI as the preferred initial integration.

Requirements:

- Store API keys in environment variables.
- Never expose API keys in the frontend.
- Use structured outputs for machine-readable plans.
- Validate AI-generated arguments before calling backend tools.
- Implement clear tool definitions.
- Handle provider errors.
- Handle rate limits.
- Avoid duplicate tool execution.
- Track AI action status.
- Log relevant operational errors without exposing secrets.

The system should support a deterministic mock AI mode for local demonstrations when a paid AI API is unavailable.

Mock mode must be clearly labeled.

## Separation of Responsibilities

The AI should handle:

- Natural-language understanding
- Personalization
- Explanation
- Proposal generation
- Conversational interaction

The backend should handle:

- Database operations
- Permissions
- Trip ownership
- Budget calculations
- Scheduling validation
- Dependency graph analysis
- Approval enforcement
- Booking state transitions
- Audit logs

Do not rely on the language model to enforce application security or data integrity.

---

# 12. DATABASE DESIGN

Inspect existing models before creating or modifying tables.

The application should support the following conceptual entities.

## Users

- ID
- Display name
- Email or local demo identifier
- Preferred communication style
- Created timestamp

## User Preferences

- ID
- User ID
- Preference category
- Preference value
- Explicitly saved flag
- Updated timestamp

## Trips

- ID
- Owner ID
- Name
- Destination
- Start date
- End date
- Budget
- Currency
- Status
- Created timestamp

## Trip Members

- ID
- Trip ID
- User or demo member ID
- Role
- Individual budget
- Preferences

## Itinerary Items

- ID
- Trip ID
- Date
- Start time
- End time
- Title
- Description
- Location
- Latitude
- Longitude
- Estimated cost
- Currency
- Item type
- Status
- Assigned members

## Reservations

- ID
- Trip ID
- Provider
- Reservation type
- Booking reference
- Start time
- End time
- Status
- Simulated flag
- Estimated cost

## Conversations

- ID
- User ID
- Trip ID
- Created timestamp

## Chat Messages

- ID
- Conversation ID
- Sender
- Content
- Timestamp
- Optional tool-call metadata

## Proposals

- ID
- Trip ID
- Proposal type
- Proposed changes
- Status
- Created timestamp
- Approved timestamp

## Disruption Events

- ID
- Trip ID
- Reservation ID
- Disruption type
- Details
- Timestamp

## Recovery Plans

- ID
- Disruption ID
- Strategy
- Proposed actions
- Estimated cost
- Status

## Audit Logs

- ID
- Trip ID
- Actor
- Action
- Target
- Result
- Timestamp

Additional entities may be necessary for group preferences, SideQuest plans, SplitQuest subgroup assignments, dependency edges, and execution records.

Use proper relationships, indexes, and foreign keys.

Preserve existing schema compatibility.

---

# 13. API REQUIREMENTS

Inspect existing routes first and reuse them when possible.

Organize endpoints logically.

Suggested API areas:

## Trips

- Create trip
- List trips
- Get trip
- Update trip
- Delete trip
- Get trip itinerary

## Itinerary

- Add item
- Update item
- Delete item
- Reorder items
- Validate schedule
- Apply approved changes

## AI Buddy

- Send message
- Retrieve conversation history
- Generate structured proposal
- Approve proposal
- Reject proposal

## Preferences

- List preferences
- Add preference
- Update preference
- Delete preference

## Dream-to-Trip

- Parse travel request
- Suggest destinations
- Generate itinerary
- Save approved itinerary

## SideQuest

- Generate SideQuest
- Retrieve SideQuest
- Regenerate SideQuest
- Approve and save SideQuest

## Groups

- Create group
- Add member
- Update member preferences
- Generate Group Harmony plan
- Approve group itinerary

## SplitQuest

- Generate subgroup plans
- Update subgroup assignments
- Change reunion details
- Approve SplitQuest

## Domino Rescue

- Simulate disruption
- Get affected reservations
- Generate recovery options
- Approve recovery plan
- Execute approved recovery
- Get execution history

Use consistent API responses and HTTP status codes.

Provide clear validation errors.

Document endpoints through FastAPI OpenAPI documentation.

---

# 14. DATA INTEGRITY AND SAFETY

The application must distinguish:

- AI-generated suggestions
- Estimated costs
- Verified information
- Saved itinerary plans
- Confirmed reservations
- Simulated reservations

Do not falsely claim to have booked, canceled, refunded, or changed a real reservation.

Require explicit user approval before:

- Modifying confirmed bookings
- Canceling reservations
- Executing recovery actions
- Making purchases
- Applying consequential shared itinerary changes

Validate user authorization for trip and group data.

Prevent unauthorized access to other users' information.

Sanitize and validate inputs.

Treat external provider data and user-uploaded content as untrusted.

Keep secrets out of logs and source control.

---

# 15. DEMO DATA

Create a reproducible hackathon demo.

Use fictional travelers and clearly labeled mock data.

## Demo Scenario

Destination: Japan

Travelers:

Alex:
- Nature and photography
- Moderate budget
- Relaxed pace

Jordan:
- Anime and shopping
- Higher budget
- Busy pace

Sam:
- Food and culture
- Moderate budget
- Balanced pace

## Demonstration Flow

### Scene 1 — Dream-to-Trip

User says:

"Plan a five-day Japan trip for three friends. We love food, nature, anime, and photography."

The AI generates an itinerary.

### Scene 2 — Memory

User says:

"Remember that I prefer quieter places and don't like waking up too early."

The preference is saved.

The user requests a new recommendation.

The AI demonstrates that it used the saved preference.

### Scene 3 — Group Harmony

The application analyzes all three travelers' interests.

It generates a balanced group itinerary and explains compromises.

### Scene 4 — SplitQuest

Two travelers choose shopping.

One traveler chooses a museum or cultural experience.

The application generates subgroup itineraries with a proposed reunion point.

### Scene 5 — SideQuest

The travelers have 90 minutes free.

The AI generates a short activity plan with estimated timing and costs.

The user approves and saves it.

### Scene 6 — Domino Rescue

A mock connecting flight is canceled.

The application:

1. Shows the disruption.
2. Displays affected reservations.
3. Explains the dependency chain.
4. Generates recovery options.
5. Requests user approval.
6. Executes mock reservation changes.
7. Updates the itinerary.
8. Shows an audit trail.

All six features should operate on the same persisted demo trip.

---

# 16. TESTING REQUIREMENTS

## Backend Tests

Test:

- Trip creation and retrieval
- Database persistence
- Itinerary creation and updates
- User preference persistence
- AI proposal validation
- Proposal approval enforcement
- Schedule conflict detection
- Group preference scoring
- SplitQuest subgroup assignments
- Reunion feasibility
- SideQuest scheduling
- Disruption dependency traversal
- Recovery ranking
- Mock booking execution
- Duplicate action protection
- Authorization boundaries

## Frontend Tests

Verify:

- Pages load correctly
- Navigation works
- Forms validate inputs
- API requests function
- Saved trips survive refresh
- Chat displays messages
- Proposed actions can be approved or rejected
- Group plans render correctly
- Errors are displayed
- Mobile layout works

## End-to-End Tests

At minimum, validate the full hackathon demo:

Create trip → Save itinerary → Save preference → Generate group plan → Generate SplitQuest → Save SideQuest → Simulate cancellation → Approve recovery → Verify database changes.

Use deterministic test fixtures.

Never report passing tests without actually running them.

---

# 17. HACKATHON DEVELOPMENT STRATEGY

This is a hackathon, so prioritize a working demonstration over production-scale infrastructure.

Implement the project in phases.

## Phase 0 — Repository Audit

- Inspect current project.
- Read existing specifications.
- Identify working components.
- Identify missing components.
- Check backend and frontend tests.
- Create an implementation plan.
- Do not modify code yet.

## Phase 1 — Core Trip Experience

- Complete frontend foundation.
- Implement dashboard.
- Implement trip creation.
- Implement itinerary management.
- Connect frontend and backend.
- Ensure database persistence.

## Phase 2 — Dream-to-Trip

- Implement natural-language trip requests.
- Implement structured AI itinerary generation.
- Add destination suggestions.
- Build itinerary review and approval.
- Save generated trips.

## Phase 3 — Travel Buddy with Memory

- Implement conversational interface.
- Connect AI to saved trip context.
- Add persistent user preferences.
- Add backend tool calling.
- Implement proposal approval workflow.

## Phase 4 — Group Harmony

- Implement group members.
- Store member preferences.
- Implement group preference scoring.
- Generate balanced itineraries.
- Explain tradeoffs.

## Phase 5 — SplitQuest

- Implement subgroup assignment.
- Generate separate activity plans.
- Calculate reunion feasibility.
- Display subgroup routes.
- Save approved plans.

## Phase 6 — SideQuest

- Generate mini-adventures.
- Use location, budget, and time constraints.
- Validate schedule compatibility.
- Add approved SideQuests to itinerary.

## Phase 7 — Domino Rescue

- Reuse existing recovery functionality.
- Complete dependency graph logic.
- Implement disruption simulation.
- Generate ranked recovery options.
- Implement approval and mock execution.
- Update itinerary and audit trail.

## Phase 8 — UI Polish

- Improve visual consistency.
- Add loading and empty states.
- Improve mobile responsiveness.
- Add useful animations.
- Polish maps, cards, and AI chat.
- Improve error handling.

## Phase 9 — Final Hackathon Demo

- Seed reproducible demo data.
- Run all tests.
- Fix critical issues.
- Validate all six features together.
- Write startup instructions.
- Prepare a three-minute demonstration.
- Document mock versus real integrations.

**Do not implement all phases simultaneously.**

At the end of each phase:

1. Explain what was implemented.
2. List files changed.
3. Run relevant tests.
4. Report test results.
5. Provide exact startup commands.
6. Identify remaining limitations.
7. Stop and wait for approval before proceeding.

---

# 18. DEFINITION OF DONE

TripRescue is ready for the hackathon when:

- The frontend and backend start reliably.
- Users can create and save trips.
- Dream-to-Trip generates editable itineraries.
- The AI buddy understands saved trip context.
- User preferences persist.
- Group Harmony produces explainable group plans.
- SplitQuest produces subgroup plans with a feasible reunion.
- SideQuest produces a usable mini-adventure.
- Domino Rescue analyzes a disruption and executes approved mock recovery actions.
- All approved changes persist in the database.
- The interface works on desktop and mobile.
- The demonstration can be repeated reliably.
- There are no dead buttons in the demonstrated flows.
- Simulated functionality is clearly identified.
- Automated tests pass.
- The README contains accurate setup instructions.

---

# 19. FINAL DEVELOPMENT INSTRUCTIONS

You are acting as the lead full-stack engineer, AI engineer, product designer, and technical architect for TripRescue.

Make technically sound decisions.

Prioritize:

1. Working functionality
2. AI integration
3. Consistent shared data
4. Clear user experience
5. Reliability
6. Demo quality
7. Visual polish

Do not silently substitute mock functionality for real integrations.

Do not implement fake UI interactions that appear functional but do not modify application state.

Do not make unnecessary architectural changes.

Do not delete existing working features.

Do not expose API keys.

Do not create unsupported claims about bookings or travel information.

When something cannot be implemented, explain the limitation and provide a practical alternative.

**START NOW WITH PHASE 0 ONLY.**

Inspect the existing TripRescue repository and its current implementation.

Then provide:

1. A summary of the existing architecture.
2. A list of working features.
3. A list of missing features.
4. Recommended database changes.
5. Recommended API changes.
6. AI integration requirements.
7. Any dependencies or API keys needed.
8. A realistic phase-by-phase implementation plan.
9. Potential technical risks.
10. The exact first implementation task.

Do not write or modify application code during Phase 0.

Wait for my approval before beginning Phase 1.