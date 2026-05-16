## MODIFIED Requirements

### Requirement: Management high-privilege operations

High-privilege management operations SHALL require an authenticated admin role, an active management relay session, and a one-time ACTION_ACK bound to the exact action, target and payload hash.

#### Scenario: Action ACK is consumed once

- **WHEN** an admin calls a high-risk endpoint with a valid ACTION_ACK
- **THEN** the server consumes the ACK before executing the action
- **AND** replaying the same ACK fails.

### Requirement: Super admin device trust

The system SHALL require a real device public key for super admin management access.

#### Scenario: Placeholder signature is rejected

- **WHEN** a super admin sends an SA_HELLO frame with a placeholder or invalid signature
- **THEN** the server rejects the frame.

### Requirement: Controlled server operations

The system SHALL expose only allowlisted server operations to super admin users with an active relay and one-time ACK.

#### Scenario: Unsupported command is blocked

- **WHEN** a user attempts to run a command id outside the allowlist
- **THEN** the server rejects the request and writes no command output to the client.
