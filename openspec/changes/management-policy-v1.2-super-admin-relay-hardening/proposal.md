# Management Policy V1.2 Super Admin Relay Hardening

## Why

The existing management module is a skeleton. It demonstrates super admin and relay concepts but does not provide a secure high-privilege management baseline.

## What Changes

- Replace placeholder signature acceptance with ECDSA P-256 device signatures.
- Persist management nonces to reject replay after restart or across processes.
- Bind ACTION_ACK to action type, target, payload hash, role and device, then consume it once.
- Require active management relay for management reads and one-time ACTION_ACK for high-risk changes.
- Add a controlled server ops panel instead of a browser raw SSH terminal.
- Add V1.7.4 deployment bundle for VPS validation without storing credentials.

## Impact

- Management UI must enroll a real browser device key before entering the console.
- Existing admin write calls must request ACTION_ACK headers.
- Web SSH remains disabled by default.
