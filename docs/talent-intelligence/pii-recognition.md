# PII recognition and masking

The local recognizer covers labeled English and Vietnamese names and addresses, email, phones, date of birth, personal URLs, LinkedIn, GitHub, Vietnamese citizen identifiers, and passport-like identifiers. Name matching is conservative and label-dependent.

Stable placeholders are assigned by entity type and first occurrence, such as `[EMAIL_1]`. Repeated case-insensitive values reuse the same placeholder. The reversible map is encrypted separately. An independent post-mask detector blocks downstream access when high-confidence PII remains.
