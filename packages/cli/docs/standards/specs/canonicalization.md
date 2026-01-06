# Canonicalization Specification

> **Status:** Draft | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

## Purpose

This specification defines deterministic serialization and hashing rules for Motus artifacts. Implementations MUST follow these rules to produce portable, verifiable hashes.

## Scope

Applies to:
- Evidence manifest (`manifest.json`)
- Gate plans
- Plan seals
- Any artifact that is hashed or signed

## JSON Canonicalization

Motus uses a subset of [RFC 8785 (JCS)](https://tools.ietf.org/html/rfc8785):

### Rules

1. **Key Ordering:** Object keys MUST be sorted lexicographically (Unicode code point order)
2. **No Whitespace:** No spaces or newlines between tokens
3. **String Escaping:** Use `\uXXXX` for control characters; no unnecessary escaping
4. **Numbers:** No leading zeros; no trailing zeros after decimal; no `+` sign
5. **No Comments:** JSON only (no JSONC, JSON5, etc.)
6. **Encoding:** UTF-8 without BOM

### Example

Input (pretty-printed):
```json
{
  "zebra": 1,
  "alpha": 2,
  "nested": {
    "b": true,
    "a": false
  }
}
```

Canonical output:
```json
{"alpha":2,"nested":{"a":false,"b":true},"zebra":1}
```

## Hash Algorithm

- **Algorithm:** SHA-256
- **Input:** Canonical JSON bytes (UTF-8)
- **Output:** Lowercase hexadecimal string (64 characters)

### Pseudocode

```
function hash(object):
    canonical_json = canonicalize(object)
    bytes = utf8_encode(canonical_json)
    return lowercase_hex(sha256(bytes))
```

## Verification

To verify a hash:

1. Parse the artifact as JSON
2. Re-canonicalize using the rules above
3. Compute SHA-256 of the canonical bytes
4. Compare to the claimed hash (case-insensitive)

## Test Vectors

See [conformance/vectors/](../conformance/vectors/) for test cases.

## Security Considerations

- Implementations MUST reject non-UTF-8 input
- Implementations MUST reject duplicate keys
- Hash comparison MUST be constant-time to prevent timing attacks
