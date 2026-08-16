# Abuse suite (loopback API process)

| Case | Input | Status | Error code | Honest |
|---|---|---|---|---|
| zero_images | no image parts | 422 | validation | yes |
| eleven_images | 11 PNGs | 422 | validation | yes |
| 25mb_image | 25 MiB PNG-prefixed blob | 422 | validation | yes |
| not_an_image | `not-an-image` named `.png` | 422 | malformed_content | yes |
| lying_png_header | PNG magic + IHDR, garbage IDAT | 201 then BLOCKED | BLOCKED | yes |
| zip_renamed_jpg | `PK\\x03\\x04` named `.jpg` | 422 | validation | yes |
| decompression_bomb | PNG IHDR 7000×7000 | 422 | malformed_content | yes |
| svg | `<svg…>` | 422 | validation | yes |
| zero_byte | empty `.png` | 422 | malformed_content | yes |
| duplicate_filenames | two PNGs both `same.png` | 201 | — | yes |
| 100kb_text | 100 KiB text field | 422 | validation | yes |
| 500_tags | 500 tag fields | 422 | validation | yes |
| nul_byte_text | NUL in text | 422 | validation | yes |
| control_char_tag | `\\x01` in a tag | 422 | validation | yes |
| rtl_override_tag | U+202E in a tag | 422 | validation | yes |
| 10000_char_tag | 10 000-character tag | 422 | validation | yes |
| client_search_id_not_uuid | `not-a-uuid-key` | 201 | — (idempotency key) | yes |
| search_id_path_traversal | `../../etc/passwd` | 404 | not_found | yes |
| result_id_path_traversal | `../../etc/passwd` | 404 | not_found | yes |
| filename_path_traversal | upload named `../../etc/passwd` | 422 | validation | yes |
| unknown_uuid_search | random UUID | 404 | search_not_found | yes |
| deleted_search | id after DELETE | 404 | search_not_found | yes |
| last_event_id_negative | `Last-Event-ID: -1` | 200 | treated as 0 | yes |
| last_event_id_huge | `Last-Event-ID: 999999999999` | 200 | empty replay | yes |
| last_event_id_non_number | `Last-Event-ID: nope` | 200 | treated as 0 | yes |
| ten_concurrent_searches | 10 POSTs at once | 201 | all BLOCKED | yes |
| sse_client_disappears | open SSE, drop client | 200 | campaign BLOCKED | yes |
| twenty_sse_readers | 20 readers on one search | 200 | all saw complete | yes |
| cancel_early | cancel just after create | 200 | CANCELLED | yes |
| cancel_after_first_event | cancel after first SSE chunk | 200 | CANCELLED | yes |
| cancel_after_terminal | cancel a BLOCKED search | 200 | stays BLOCKED | yes |
| delete_during_stream | DELETE while SSE open | 204 | later GET search_not_found | yes |
| refresh_terminal_repeatedly | 5× POST refresh | 202 | refreshed=false | yes |
| per_object_cap | file over `MAX_UPLOAD_BYTES` | 422 | validation | yes |
| per_search_byte_budget | combined over total cap | 422 | validation | yes |
| disk_margin | `DISK_MARGIN` above free space | 422 | validation | yes |

Responses never echoed `/Users`, `/tmp`, or `/etc/passwd` file contents.
Machine-readable body is always `{ "error", "detail" }` on error paths.
