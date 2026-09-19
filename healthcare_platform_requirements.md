# Autonomous Multi-Hospital Patient Intake, Scheduling & Pre-Visit Voice Agent

## 1. Project Overview

Build a **multi-tenant, AI-native healthcare access and operations platform** where multiple hospitals can configure:

- Services
- Departments
- Specialties
- Doctors
- Calendars
- Availability
- Questionnaires
- Healthcare-system integrations
- Workflows
- Communication preferences

Patients should interact naturally with the platform through a conversational AI interface, primarily through **web voice** and **telephone**.

The system must allow a patient to describe an administrative healthcare request in natural language, for example:

> "I need to see a doctor for my shoulder pain sometime this week."

The AI should:

1. Understand the administrative intent.
2. Ask for missing information.
3. Discover relevant hospitals/doctors.
4. Check **real availability**.
5. Present suitable options.
6. Execute authorized application actions.
7. Integrate with the configured healthcare system.
8. Verify the external result.
9. Synchronize internal state.
10. Trigger questionnaires, reminders, notifications, and workflows.
11. Provide visibility to doctors and administrators.

The AI is an **administrative assistant** and must not make clinical decisions.

---

# 2. Product Goal

The platform should demonstrate this complete chain:

```text
Patient Request
    ↓
AI Understanding + Context
    ↓
Hospital / Doctor Discovery
    ↓
Real Availability
    ↓
Authorized Action
    ↓
Healthcare-System Integration
    ↓
External Verification
    ↓
State Synchronization
    ↓
Workflow / Questionnaire / Notification
    ↓
Doctor + Admin Visibility
```

The project should feel like a **small but coherent healthcare platform**, not a chatbot, CRUD appointment application, or collection of unrelated demos.

The priority is:

> **Depth of one complete reliable workflow over breadth of disconnected features.**

---

# 3. Core Product Principles

The implementation must follow these principles:

1. **Real availability**  
   AI must use actual scheduling data and must never invent slots.

2. **Clarification over guessing**  
   Ambiguous patient requests must be clarified.

3. **AI is administrative**  
   The AI must not diagnose, prescribe, recommend treatment, change medication, or make independent clinical assessments.

4. **Hospital-controlled configuration**  
   Hospital rules determine what can be booked.

5. **Doctor-controlled availability**  
   Doctor calendars, blocked periods, and leave must be respected.

6. **Capability-based actions**  
   AI actions must happen through controlled application capabilities.

7. **External verification**  
   The system must not report a successful appointment until the external result is verified where an external healthcare system is involved.

8. **Tenant isolation**  
   One hospital must never access another hospital's private data.

9. **Useful context**  
   Preserve relevant appointment and preference context without unnecessarily storing sensitive information.

10. **Observable operations**  
    Important actions must be traceable.

11. **Recoverable failures**  
    Integration and workflow failures must have explicit recovery behavior.

12. **Privacy-aware design**  
    Healthcare information should not unnecessarily appear in logs or AI context.

---

# 4. Required Technology Stack

## Frontend

- React
- Tailwind CSS

The frontend should be designed independently and creatively by the implementation model.

The UI should be:

- Beautiful
- Professional
- Modern
- Polished
- Responsive
- Intuitive
- Production-quality
- Healthcare-appropriate

Do not prescribe a fixed visual style. The implementation should use its own professional design judgment.

## Backend

- Python
- FastAPI
- PostgreSQL

## AI

- LangChain
- LangGraph
- MCP (Model Context Protocol)
- Grok API

The Grok API key will be provided through environment variables.

## Voice

The platform must support:

- Speech-to-Text
- AI processing
- Text-to-Speech
- Real-time conversational interaction

The voice layer must remain modular so voice providers can be replaced later if necessary.

## Infrastructure

- Docker
- Docker Compose

Docker must be part of the application architecture from the beginning, not added only at the end.

---

# 5. Docker Requirements

The complete local system must be runnable using Docker Compose.

Provide:

- `Dockerfile` for frontend
- `Dockerfile` for backend
- `docker-compose.yml`
- Environment configuration
- PostgreSQL persistent volume
- Container networking
- Health checks
- Service dependencies
- Reproducible startup
- Database initialization
- Migration support
- Seed-data support

The primary development flow should work with:

```bash
docker compose up --build
```

The host machine should not need to manually install the project's Python packages, Node dependencies, or PostgreSQL for the primary Docker workflow.

Use:

```text
.env
.env.example
```

Never hardcode secrets.

---

# 6. Logical Architecture

Use a clear separation of concerns:

```text
Interfaces
    ↓
Application / AI
    ↓
Context + Capabilities
    ↓
Core Services
    ↓
Scheduling
    ↓
Integration / Connectors
    ↓
External Systems
    ↓
Verification / Synchronization
    ↓
Events / Workflows
    ↓
Data / Analytics / Observability
```

Required architectural principles:

- AI logic must not contain vendor-specific EHR logic.
- Scheduling must remain independent from conversation logic.
- External healthcare integrations must be behind connectors/interfaces.
- Long-running workflows should be asynchronous.
- Operational events must be separate from transactional records.
- AI actions must be structured and auditable.

---

# 7. AI Architecture

Use **LangChain + LangGraph + MCP** as real architectural components.

The AI should not be a single monolithic function.

A conceptual flow:

```text
Patient Request
    ↓
Intent / Request Understanding
    ↓
Context Retrieval
    ↓
Clarification if Needed
    ↓
Hospital / Doctor Discovery
    ↓
Availability
    ↓
Patient Selection / Confirmation
    ↓
Authorized Capability
    ↓
Scheduling
    ↓
External Integration
    ↓
Verification
    ↓
Synchronization
    ↓
Workflow / Questionnaire
```

## LangGraph

Use explicit graph state and conditional routing.

Potential nodes:

- Intent detection
- Context retrieval
- Clarification
- Hospital discovery
- Doctor discovery
- Availability
- Patient selection
- Booking
- Verification
- Synchronization
- Questionnaire
- Workflow initiation
- Human escalation

## LangChain

Use it for appropriate LLM orchestration, prompts, structured outputs, and AI application components.

## MCP

MCP must expose controlled healthcare application capabilities to the AI.

Do not use MCP only as a decorative technology.

---

# 8. AI Capabilities

Expose controlled capabilities such as:

- `search_hospitals`
- `search_doctors`
- `check_availability`
- `lookup_patient`
- `get_appointment`
- `create_appointment`
- `reschedule_appointment`
- `cancel_appointment`
- `get_questionnaire`
- `submit_questionnaire`
- `send_notification`
- `start_workflow`
- `get_context`
- `update_preferences`
- `verify_external_appointment`
- `synchronize_state`
- `transfer_to_human`

Every capability should define:

- Input schema
- Output schema
- Validation
- Authorization
- Error handling
- Retry behavior where required
- Idempotency where required
- Verification where required
- Audit information

The AI must never directly access the database or EHR.

---

# 9. AI Context and State Management

Keep these state categories separate:

1. Transactional state
2. Conversational state
3. User context
4. Workflow state
5. Integration state
6. Operational state

Conversational state may contain:

- Current intent
- Selected hospital
- Selected doctor
- Selected slot
- Current appointment
- Relevant preferences
- Communication preferences
- Completed workflow state

Do not store the entire application state as one unstructured AI memory object.

Business state must remain explicitly represented in the application's data model.

---

# 10. User Roles

The platform has four primary roles.

## Platform Admin

Responsibilities:

- Approve hospitals
- Manage global configuration
- Monitor platform health
- Monitor AI
- Monitor integrations
- Monitor workflows
- View analytics
- View AI evaluation
- View audit

## Hospital Admin

Responsibilities:

- Configure hospital
- Manage doctors
- Configure calendars
- Configure availability
- Configure questionnaires
- Configure integrations
- Configure workflows
- Manage staff/access

## Doctor

Responsibilities:

- Manage own availability
- Manage own calendar
- View appointments
- View authorized pre-visit information

## Patient

Responsibilities:

- Register/login
- Manage profile
- Manage appropriate preferences
- Discover providers
- Book appointments
- Reschedule appointments
- Cancel appointments
- Complete questionnaires
- Manage preferences

---

# 11. Multi-Tenant Requirements

Tenant boundaries are mandatory.

A hospital administrator may manage their own hospital but must not access another hospital's private:

- Configuration
- Patient information
- Conversations
- Questionnaires
- Appointments
- Integration data
- AI activity

Server-side authorization must enforce tenant boundaries.

---

# 12. Hospital Onboarding

Hospital lifecycle:

```text
Draft
  ↓
Submitted
  ↓
Under Review
  ↓
Approved / Rejected
```

Hospital registration should support concepts such as:

- Hospital / organization name
- Address
- Contact information
- Departments
- Specialties
- Services
- Operating hours
- Administrator information
- Supported healthcare systems
- Integration configuration

Only approved hospitals can:

- Create active doctors
- Publish availability
- Receive appointments
- Enable production integrations

Platform admins must be able to:

- Review applications
- Approve
- Reject
- Request corrections
- Suspend
- Reactivate
- View hospital activity

---

# 13. Hospital Configuration

Hospital admins should manage:

- Hospital profile
- Departments
- Specialties
- Doctors
- Appointment types
- Consultation duration
- Calendars
- Working hours
- Availability
- Blocked periods
- Questionnaires
- Communication preferences
- Workflows
- Healthcare-system configuration

---

# 14. Doctor Configuration

Doctor information should support:

- Name
- Photo
- Specialty
- Department
- Qualifications
- Experience
- Languages
- Consultation types
- Appointment duration
- Hospital
- External provider ID
- Status

Doctor lifecycle:

```text
Invited
  ↓
Active
  ↓
Inactive / Suspended
```

Only active doctors with valid availability may receive appointments.

---

# 15. Scheduling and Availability

Scheduling is the central source of truth for bookable slots.

A slot is available only when:

- Doctor is active
- Calendar is active
- Slot is within working hours
- Slot is not blocked
- Doctor is not on leave
- Slot is not already booked
- Appointment type is compatible
- External scheduling constraints are satisfied where applicable

The AI must never invent availability.

The system must prevent concurrent double booking through:

- Transactions
- Locking
- Reservation
- Conflict detection

Use whatever mechanism is appropriate for the implementation.

Availability must be revalidated immediately before booking when required.

---

# 16. Appointment Management

Support:

- Create
- Confirm
- Retrieve
- Reschedule
- Cancel
- Notify
- Synchronize
- Reconcile

Suggested appointment states:

- Requested
- Pending
- Confirmed
- Rescheduled
- Cancelled
- Completed
- No-show
- Failed
- Synchronization Pending
- Reconciliation Required

Every appointment should maintain appropriate history and internal/external identifiers.

---

# 17. Booking Flow

A normal booking flow:

```text
Patient Request
    ↓
AI understands intent
    ↓
Clarification if needed
    ↓
Hospital / Doctor Discovery
    ↓
Real Availability
    ↓
Patient selects slot
    ↓
Authorized booking action
    ↓
External healthcare-system operation
    ↓
External verification
    ↓
Internal synchronization
    ↓
Patient confirmation
```

The patient must not receive a final confirmation until the appointment result has been verified where external integration is involved.

---

# 18. Mock EHR / Healthcare-System Integration

The prototype must include a **Mock EHR / Mock Healthcare System**.

Architecture:

```text
AI
 ↓
MCP Capability
 ↓
Scheduling / Appointment Service
 ↓
Integration Layer
 ↓
Connector
 ↓
Mock EHR
```

The architecture must allow a real connector to replace the mock connector later.

Required operations:

- Patient lookup
- Provider lookup
- Facility/department lookup
- Calendar lookup where applicable
- Availability lookup where supported
- Appointment creation
- Appointment update
- Appointment cancellation
- Appointment rescheduling
- Appointment retrieval
- Appointment verification

Maintain mappings:

```text
Internal Patient ↔ External Patient
Internal Doctor ↔ External Provider
Internal Appointment ↔ External Appointment
Internal Facility ↔ External Facility
```

---

# 19. Verification, Failure Recovery and Reconciliation

A successful API response does not automatically mean the external operation succeeded.

For booking:

```text
Create Appointment
    ↓
External Response
    ↓
Verify External Record
    ↓
Synchronize Internal State
    ↓
Confirm to Patient
```

Handle:

- Timeout
- Network failure
- Authentication failure
- Authorization failure
- Rate limiting
- External-system outage
- Validation errors
- Mapping errors
- Missing patient
- Missing provider
- Slot conflict
- Duplicate request
- Partial success
- Unknown outcome

## Unknown Outcome

Example:

```text
Create Appointment
    ↓
Timeout
    ↓
Did external system create it?
    ↓
Query external system
    ↓
Found → Sync Safely
Not Found → Safely Retry
```

Never blindly retry an operation that could create a duplicate appointment.

Unresolved cases must become:

- Reconciliation records
- Human escalations

---

# 20. Required Failure Demonstration

Demonstrate at least one meaningful failure/recovery path.

### Preferred scenario

```text
Booking Sent
    ↓
Network Timeout
    ↓
Unknown Result
    ↓
Query Mock EHR
    ↓
Appointment Found
    ↓
Synchronize
    ↓
Do NOT Create Duplicate
```

Alternative recovery scenario:

```text
EHR Failure
    ↓
Retries Exhausted
    ↓
External State Check
    ↓
Reconciliation Record
    ↓
Human Escalation
    ↓
Operational Dashboard
```

This failure path should be visible in the platform.

---

# 21. Patient Management

Patients should be able to:

- Register/login
- Manage profile
- Manage appropriate preferences
- View appointments
- Book appointments
- Reschedule
- Cancel
- Complete questionnaires

Patient data may include:

- Name
- Contact information
- Date of birth
- Communication preference
- Relevant profile information
- Appointment history
- External patient ID where applicable

Follow data minimization.

Do not store information simply because it is available.

---

# 22. Patient AI Access Agent

The AI is the primary patient-access interface.

It should support:

- Natural-language understanding
- Administrative intent detection
- Clarification
- Hospital discovery
- Doctor discovery
- Availability lookup
- Booking
- Rescheduling
- Cancellation
- Appointment lookup
- Questionnaire collection
- Notification/workflow initiation
- Context retrieval
- External verification
- Human escalation

The AI should be reusable across:

- Web voice
- Telephone
- Future channels

---

# 23. Voice and Telephone

Support a real-time conversational voice experience.

Conceptual flow:

```text
Patient
    ↓
Audio / Telephone
    ↓
Speech Recognition
    ↓
AI Agent
    ↓
Capabilities
    ↓
Scheduling / Integration
    ↓
Speech Generation
    ↓
Patient
```

Voice requirements include:

- Streaming where practical
- Turn-taking
- Interruption / barge-in
- Silence handling
- Reasonable latency
- Long-running operation handling
- Call failure handling

A target of sub-2-second perceived latency for normal conversational turns is desirable where technically achievable.

Telephone functionality should support:

- Inbound calls
- Patient identification
- Appointment lookup
- Booking
- Rescheduling
- Cancellation
- Failure handling
- Human escalation

---

# 24. AI Safety Boundaries

The AI may:

- Find hospitals
- Find doctors
- Find appointments
- Book appointments
- Reschedule/cancel
- Answer approved administrative questions
- Ask approved pre-visit questions
- Record patient responses
- Trigger workflows
- Communicate appointment status
- Escalate to humans

The AI must not:

- Diagnose
- Prescribe
- Change medication
- Recommend treatment
- Make independent clinical assessments
- Invent clinical information

The AI should distinguish between patient-reported information and unsupported clinical conclusions.

Example:

```text
"You reported chest discomfort."
```

is allowed.

```text
"You have a heart condition."
```

is an unsupported clinical conclusion and is not allowed.

---

# 25. Pre-Visit Questionnaire

Hospital/doctor administrators can configure approved questionnaires.

Supported question types:

- Yes/no
- Choice
- Multiple choice
- Numeric
- Date
- Short text
- Long text
- Structured fields

Questionnaires may be associated with:

- Hospital
- Specialty
- Doctor
- Appointment type
- Approved condition/category

The AI can collect answers conversationally and store structured responses.

Flow:

```text
Appointment Booked
    ↓
Questionnaire Assigned
    ↓
AI Collects Responses
    ↓
Structured Responses
    ↓
Doctor Reviews
```

Do not use the questionnaire system for:

- Diagnosis
- Prescribing
- Medication changes
- Independent clinical assessment

Potentially urgent information should follow a predefined escalation policy.

---

# 26. Workflow and Event Automation

Support asynchronous and scheduled workflows.

Important events may include:

- Hospital approved
- Doctor created
- Appointment booked
- Appointment cancelled
- Appointment rescheduled
- Questionnaire assigned
- Questionnaire completed
- AI conversation started
- Capability executed
- EHR operation started/completed/failed
- External verification completed
- Reconciliation required
- Workflow started/completed/failed
- Human escalation

Events can trigger:

- Notifications
- Reminders
- Questionnaires
- Synchronization
- Recovery
- Analytics
- Audit
- Evaluation

Workflows should support:

- Delays
- Conditions
- Retries
- Idempotency
- Execution history
- Failure states

---

# 27. Notifications

## Patient

- Appointment confirmation
- Reminder
- Cancellation
- Rescheduling
- Questionnaire reminder
- Important updates

## Doctor

- New appointment
- Cancellation
- Rescheduling
- Questionnaire completion
- Upcoming appointment

## Hospital

- Application status
- Appointment activity
- Integration failures
- Operational alerts

The prototype may use a lightweight/mock delivery service where appropriate.

---

# 28. Dashboard Requirements

Provide role-specific dashboards.

## Platform Admin Dashboard

Should provide visibility into:

- Hospital applications
- Hospitals
- Doctors
- Patients
- Appointments
- AI activity
- Integration activity
- Workflows
- Analytics
- AI evaluation
- Operational health
- Audit logs

## Hospital Admin Dashboard

Should provide access to:

- Hospital overview
- Appointments
- Doctors
- Calendars
- Availability
- Questionnaires
- AI activity
- Integration activity
- Workflows
- Analytics
- Integrations
- Staff/access management

## Doctor Dashboard

Should provide:

- Today's appointments
- Upcoming appointments
- Calendar
- Availability
- Blocked time
- Appointment details
- Questionnaires
- Authorized pre-visit responses

## Patient Dashboard

Should provide:

- Home
- AI assistant
- Upcoming appointments
- Historical appointments
- Questionnaires
- Preferences
- Profile

Dashboards should be meaningful rather than collections of arbitrary KPI cards.

---

# 29. Frontend Pages

## Public / Authentication

- Landing Page
- Login
- Registration
- Hospital Registration
- Password Recovery / Reset

## Platform Admin

- Dashboard
- Hospital Applications
- Hospitals
- Hospital Details
- Doctors
- Patients
- Appointments
- AI Activity
- Integration Activity
- Workflow Monitoring
- Analytics
- AI Evaluation
- Operational Health
- Audit Logs
- Platform Configuration

## Hospital Admin

- Dashboard
- Hospital Overview
- Hospital Profile
- Departments
- Specialties
- Doctors
- Doctor Details
- Calendars
- Availability
- Blocked Slots
- Appointment Types
- Questionnaires
- Questionnaire Builder
- AI Activity
- Integrations
- Integration Details
- Workflows
- Workflow Details
- Notifications
- Analytics
- Staff / Access Management

## Doctor

- Dashboard
- Today's Appointments
- Upcoming Appointments
- Calendar
- Availability Management
- Blocked Time
- Appointment Details
- Patient Appointment Information
- Pre-Visit Questionnaire Responses

## Patient

- Home
- AI Assistant
- Voice Assistant
- Hospital Discovery
- Doctor Discovery
- Availability / Slot Selection
- Appointment Details
- Upcoming Appointments
- Appointment History
- Questionnaire
- Preferences
- Profile

---

# 30. UI / UX Requirements

Do not impose a specific visual style.

The implementation model should create its own design system and make the product:

- Full professional
- Beautiful
- Modern
- Polished
- Distinctive
- Consistent
- Responsive
- Easy to navigate
- Appropriate for healthcare

Avoid generic dashboard templates and unnecessary visual clutter.

Create role-specific information architecture rather than simply duplicating one dashboard for every role.

Include appropriate:

- Charts
- Tables
- Timelines
- Calendar views
- Status indicators
- Activity feeds
- Forms
- Dialogs
- Drawers
- Appointment views
- AI conversation UI
- Voice controls
- Loading states
- Error states
- Empty states
- Confirmation states

---

# 31. Dummy Data

The project must include realistic dummy data.

The application should not look empty after startup.

Seed multiple:

### Hospitals

- Multiple hospitals
- Departments
- Specialties
- Services
- Operating hours

### Doctors

- Multiple doctors
- Specialties
- Departments
- Qualifications
- Experience
- Languages
- Consultation types
- Availability

### Patients

- Multiple patients
- Profiles
- Preferences
- Appointment history

### Appointments

Include:

- Upcoming
- Confirmed
- Cancelled
- Completed
- Rescheduled
- Failed
- Synchronization Pending
- Reconciliation Required

### Scheduling

Include:

- Working hours
- Available slots
- Blocked slots
- Leave

### Questionnaires

Include several realistic administrative/pre-visit questionnaires.

### AI

Include:

- Sample conversations
- Capability executions
- Clarification examples
- Successful booking examples

### Integrations

Include:

- Healthy integration
- Failed integration
- Timeout example
- Unknown outcome example

### Workflows

Include:

- Running
- Completed
- Failed
- Scheduled

### Notifications

Include realistic examples.

### Audit

Include examples of:

- Logins
- Configuration changes
- Appointment operations
- Capability executions
- Integration operations

Create a repeatable seed command.

---

# 32. Observability and Audit

Important operations must be traceable.

A booking should be traceable across:

```text
Conversation
→ AI Decision
→ Capability
→ Scheduling
→ EHR Operation
→ Verification
→ Synchronization
→ Workflow
→ Notification
```

Use a correlation/operation ID.

## AI Metrics

Track:

- Conversations
- Latency
- Capability success/failure
- Escalation
- Usage
- Approximate cost

## Scheduling Metrics

Track:

- Booking success
- Availability
- Cancellations
- Rescheduling
- Utilization

## Integration Metrics

Track:

- Requests
- Success/failure
- Verification
- Retry
- Recovery
- Reconciliation
- Unknown outcomes

## Workflow Metrics

Track:

- Running
- Completed
- Failed
- Retried
- Duration

## Audit Events

Record important events such as:

- Login/access
- Appointment operations
- Patient-data access
- AI actions
- Capability executions
- Integration operations
- Configuration changes
- Administrative actions

Avoid unnecessarily storing raw sensitive healthcare content in operational logs.

---

# 33. Security and Privacy

Demonstrate:

- Authentication
- Authorization
- Role-based access control
- Tenant isolation
- Resource ownership
- Secure API design
- Input validation
- Secure secret management
- Audit logging
- Appropriate encryption
- Privacy-aware logging

Critical rule:

> Hospital A must never access Hospital B's private data.

The restriction also applies to:

- Patient context
- Conversations
- Questionnaires
- Appointments
- Integration data
- AI activity

Never hardcode:

- External credentials
- API keys
- Database credentials
- Voice credentials
- AI provider secrets

---

# 34. Data Model

The implementation should explicitly represent major entities including:

- Platform
- Hospital
- Hospital Admin / Staff
- Department
- Specialty
- Doctor
- Calendar
- Availability
- Blocked Slot
- Patient
- User Context / Preferences
- Appointment
- Questionnaire
- Questionnaire Response
- AI Conversation
- AI Context
- Capability
- Capability Execution
- Healthcare-System Connection
- External Identifier Mapping
- Integration Operation
- Integration Verification
- Reconciliation Record
- Workflow
- Workflow Execution
- Notification
- AI Evaluation
- Audit Event
- Operational Event

The model must support:

- Tenant isolation
- External identifiers
- State history
- Efficient lookups
- Appropriate indexing
- Clear ownership

---

# 35. Reliability and Idempotency

Protect against duplicate actions, especially:

- Appointment creation
- Appointment cancellation
- Rescheduling
- Notifications
- Workflow execution
- External integration requests

Use appropriate:

- Idempotency keys
- Correlation IDs
- Transactions
- Conflict detection
- External verification

The system must demonstrate at least one scenario where a failure occurs after an external request and the actual final state is determined safely.

---

# 36. Testing Requirements

## Unit Tests

At minimum:

- Availability calculation
- Slot validation
- Appointment state transitions
- Context resolution
- Capability validation
- Workflow conditions
- Identifier mapping
- Idempotency
- Reconciliation

## Integration Tests

At minimum:

- AI → Scheduling
- Scheduling → Appointment
- Appointment → EHR
- EHR → Verification
- Verification → Synchronization
- Booking → Workflow
- Workflow → Notification

## AI Tests

Test:

- Intent
- Context
- Clarification
- Tool/capability selection
- Invalid requests
- Unsupported requests
- Safety boundaries

## EHR Tests

Test:

- Patient mapping
- Provider mapping
- Appointment creation
- Rescheduling
- Cancellation
- Timeout
- Duplicate requests
- Unknown outcomes
- Verification
- Reconciliation

## End-to-End

Minimum successful path:

```text
Patient
→ Voice
→ AI
→ Discovery
→ Availability
→ Booking
→ Mock EHR
→ Verification
→ Synchronization
→ Questionnaire
→ Workflow
→ Doctor View
→ Admin Analytics
```

Also demonstrate at least one failure/recovery path.

---

# 37. Development Phases

## Phase 1 — Foundation

- React
- Tailwind
- FastAPI
- PostgreSQL
- Docker
- Docker Compose
- Environment configuration
- Authentication foundation
- Database connection
- Migrations
- Base models
- Seed infrastructure

## Phase 2 — Identity and Multi-Tenancy

- Users
- Roles
- Hospitals
- Hospital admins
- Doctors
- Patients
- Tenant isolation
- Authorization

## Phase 3 — Hospital and Doctor Configuration

- Hospital profile
- Departments
- Specialties
- Doctors
- Calendars
- Working hours
- Appointment types
- Availability
- Blocked periods

## Phase 4 — Scheduling

- Slot engine
- Conflict detection
- Booking
- Appointment state machine
- Rescheduling
- Cancellation

## Phase 5 — Mock EHR and Integration

- Integration abstraction
- Mock EHR
- External mappings
- Create/update/cancel/retrieve
- Verification
- Synchronization

## Phase 6 — AI Core

- LangChain
- LangGraph
- Context
- Graph state
- Prompts
- Intent
- Clarification
- Discovery
- Scheduling orchestration

## Phase 7 — MCP

- MCP server
- Capability tools
- Validation
- Authorization
- Idempotency
- Auditing
- Verification

## Phase 8 — Patient AI + Voice

- AI chat
- Speech-to-Text
- Grok
- Text-to-Speech
- Voice interface
- Booking
- Rescheduling
- Cancellation

## Phase 9 — Questionnaire + Workflows

- Questionnaire builder
- Conversational questionnaire
- Structured responses
- Workflow system
- Reminders
- Notifications

## Phase 10 — Dashboards

- Platform Admin
- Hospital Admin
- Doctor
- Patient
- Analytics
- AI activity
- Audit
- Operational monitoring

## Phase 11 — Reliability

- Timeout
- Retries
- Idempotency
- Unknown outcomes
- Reconciliation
- Human escalation
- Failure demonstrations

## Phase 12 — Testing and UX Polish

- Unit tests
- Integration tests
- AI tests
- EHR tests
- End-to-end tests
- Responsive polish
- Loading states
- Empty states
- Error states

## Phase 13 — Deployment

- Production Dockerfiles
- Docker Compose
- Environment configuration
- Health checks
- Database persistence
- Deployment configuration
- README
- Demo accounts
- Deployment instructions

---

# 38. Required Demo Journey

## Hospital

```text
Hospital registers
→ Platform Admin approves
→ Hospital configured
→ Doctor created
→ Calendar configured
→ Availability configured
→ Healthcare integration configured
```

## Patient

```text
Patient registers
→ Starts voice conversation
→ Describes requirement
→ AI understands intent
→ AI resolves context
→ AI finds hospitals/doctors
→ AI checks real availability
→ Patient selects slot
```

## Booking

```text
Appointment created
→ External healthcare system called
→ External result verified
→ Internal state synchronized
→ Patient receives confirmation
```

## Follow-Up

```text
Questionnaire assigned
→ Patient answers conversationally
→ Responses structured
→ Doctor reviews
→ Reminder/notification workflows execute
```

## Operations

```text
Admin views:
Appointments
AI activity
Integration activity
Workflow activity
Audit
Operational metrics
```

## Failure

```text
Failure
→ Classification
→ Recovery / Verification
→ Correct Final State
```

---

# 39. Definition of Done

The project is complete when the following scenario works end-to-end:

### Hospital

```text
Hospital registers
→ Admin approves
→ Hospital configured
→ Doctor created
→ Calendar configured
→ Availability configured
→ Healthcare integration configured
```

### Patient

```text
Patient registers
→ Starts voice conversation
→ Describes requirements
→ AI understands intent
→ Resolves context
→ Finds relevant doctors/hospitals
→ Checks actual availability
→ Patient selects slot
```

### Booking

```text
Appointment created
→ External healthcare system called
→ External result verified
→ Internal state synchronized
→ Patient receives confirmation
```

### Follow-Up

```text
Questionnaire assigned
→ Patient answers conversationally
→ Responses structured
→ Doctor can review
→ Reminder/notification workflows execute
```

### Operations

```text
Admin can see:
- Appointments
- AI
- Integration
- Workflow
- Audit
- Basic operational metrics
```

### Failure

At least one meaningful external or workflow failure must be demonstrated and safely recovered.

---

# 40. Submission Requirements

## 1. Deployed Application

Provide a publicly accessible deployment demonstrating the main workflow.

## 2. GitHub Repository

Include:

- Source code
- Setup instructions
- Environment template
- Database setup
- Tests
- Architecture documentation
- AI documentation
- Integration documentation
- Deployment instructions

No secrets in the repository.

## 3. Demo Video

Show the connected workflow:

```text
Hospital Setup
→ Doctor
→ Availability
→ Patient
→ AI Voice
→ Booking
→ EHR
→ Verification
→ Questionnaire
→ Workflow
→ Doctor
→ Admin
```

Also include the failure/recovery scenario.

## 4. Architecture Documentation

Include:

- High-level architecture
- Data model
- Booking sequence
- EHR integration flow
- Failure/recovery flow
- Security/tenant model

## 5. AI Documentation

Include:

- AI models
- Voice technology
- AI development tools
- Runtime AI
- Important prompts
- Evaluation approach

## 6. README

Include:

- Overview
- Features
- Architecture
- Tech stack
- Setup
- Environment variables
- AI setup
- Voice setup
- Mock EHR
- Workflows
- Tests
- Deployment
- Credentials/demo accounts
- Known limitations
- Future improvements

---

# 41. Technology Selection Expectations

No specific framework beyond the required project stack is mandated by the product requirements, but the selected architecture should be justified around:

- Prototype speed
- Reliability
- Maintainability
- AI support
- Real-time capabilities
- Integration support
- Data modeling
- Observability
- Cost
- Deployment simplicity

The evaluation focuses on engineering decisions rather than framework preference.

---

# 42. Evaluation Focus

The implementation will primarily be evaluated on:

## Product Completion

Does the main patient journey actually work?

## AI Quality

Can AI:

- Understand intent
- Maintain context
- Clarify ambiguity
- Execute appropriate capabilities

## Engineering

Is the application cleanly structured and maintainable?

## Scheduling

Does it use real availability and prevent double booking?

## Integration

Is the EHR layer properly separated and verified?

## Reliability

Can the system safely recover from failures?

## Security

Are tenant boundaries and permissions enforced?

## Observability

Can an operator understand what happened during a booking?

## UX

Does the patient experience feel conversational and natural?

## Scope Management

Was the core workflow prioritized instead of building many disconnected features?

---

# 43. Final Product Principle

The final prototype should demonstrate:

> A multi-tenant, AI-native healthcare access platform where hospitals configure services, doctors control availability, patients communicate naturally, AI understands and coordinates requests, capabilities execute authorized actions, scheduling provides real availability, healthcare-system integrations perform external operations, external results are verified, internal state is synchronized, workflows automate follow-up, and operators can observe and evaluate the complete process.

The central principle is:

> **The AI should not merely talk about performing healthcare operations. It should safely coordinate real application actions, integrate with external systems, verify outcomes, recover from failures, and leave the platform in a correct and observable state.**

---

# 44. Priority

The highest priority is:

```text
ONE COMPLETE RELIABLE WORKFLOW
```

The evaluator should be able to follow:

```text
Natural Language
    ↓
AI
    ↓
Context
    ↓
Doctor Discovery
    ↓
Real Availability
    ↓
Booking
    ↓
EHR
    ↓
Verification
    ↓
Synchronization
    ↓
Questionnaire
    ↓
Workflow
    ↓
Doctor
    ↓
Analytics / Audit
```

Then intentionally cause:

```text
Failure
    ↓
Classification
    ↓
Recovery / Verification
    ↓
Correct Final State
```

The finished system should feel like a **small, coherent, professional healthcare SaaS platform**, with the core workflow implemented deeply and reliably.
