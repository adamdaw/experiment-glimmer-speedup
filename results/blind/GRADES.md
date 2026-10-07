# Blind grades: glimmer-speed

Only `packet.md` was used as source material. No answer key or model-evaluation directory was opened. All 11 tasks and 55 answers are graded. Labels are independently shuffled per task: these averages summarize answer positions, **not identifiable models**, and must not be treated as a model ranking.

## Method

Scores are integers from 1 to 5. Correctness, groundedness, completeness and concision follow the packet rubric; 2 and 4 are intermediate judgments. Usefulness is an additional holistic score requested by the user: 5 = accurate, actionable and sufficient for the task; 4 = useful with limited repair; 3 = materially incomplete or requiring several corrections; 2 = substantial checking/rework needed; 1 = unusable/misleading. It is not an arithmetic composite. Omissions reduce completeness/usefulness; false factual assertions reduce correctness/groundedness. Repetition reduces concision. Code supplied as a proposed fix is not treated as an invented existing file or implementation.

Every task has equal weight in per-label averages (11 answers per label). Review counts are distinct planted bugs, not bullet counts. Duplicate reports of a true bug are not false alarms; they lose concision. False alarms count distinct unsupported/wrong defect reports, not each mistaken detail inside an otherwise real defect. Valid additional findings, such as unbounded cache retention and invalid page input, receive credit. Definite assertions about unseen callers/business/error contracts are not established defects. The timeout task uses the packet's eight U groups and six S groups: partial coverage of a group earns group recall but missing operations are recorded separately. All answers identify 8/8 U groups and 6/6 S groups; none misclassifies an S group as unbounded.

For the cited-explore tasks, citation errors are counted once per distinct claim/citation pairing, not once per repeated token. A citation to an existing but non-supporting line is wrong; nonexistent files/lines or asserted unseen implementations are hallucinated citations. A paragraph's explicit narrow citation is checked against all behavior attributed to it; thus citing connect line 40 for drain at line 42 is wrong even though drain exists elsewhere. Adjacent supported explanations and previously cited source blocks are accepted as context. All cited paths/ranges in these two tasks exist; no hallucinated citations were found. Unsupported behavioral claims and numerical examples are recorded separately, even when the cited file exists. Missing citations are noted as coverage limitations rather than invented citations.

The actual shown evidence takes precedence over loose reference phrasing: e2 pool utilization is not literally monotonic, and its shown 503s are on checkout/cart, not orders. No penalty for omitting an orders 503 that does not exist. Retry backoff conventions alone do not establish an off-by-one defect. No browsing or external repository inspection was used. Small arithmetic and citation-range checks used only packet text and in-memory calculations.

## Per-label averages and counts

| Label | Correctness | Groundedness | Usefulness | Completeness | Concision | Planted found | False alarms | Wrong citations | Hallucinated citations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4.00 | 3.45 | 3.91 | 4.36 | 3.64 | 10/10 | 1 | 3 | 0 |
| B | 3.73 | 3.55 | 3.82 | 4.36 | 3.64 | 10/10 | 2 | 2 | 0 |
| C | 4.09 | 3.91 | 4.09 | 4.36 | 3.82 | 10/10 | 1 | 2 | 0 |
| D | 3.73 | 3.36 | 3.64 | 4.36 | 3.64 | 10/10 | 1 | 5 | 0 |
| E | 3.91 | 3.64 | 3.82 | 4.36 | 3.82 | 10/10 | 1 | 2 | 0 |

## Per-task grades

C = correctness; G = groundedness; U = usefulness; Co = completeness; Cn = concision. A dash means the counter does not apply. Citation counters apply only to the two cited-explore tasks.

### r1_report_cache

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| B | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| C | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| D | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| E | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |

**A.** Finds missing user_id in cache key and ascending top_n; both fixes are correct.

**B.** Finds missing user_id in cache key and ascending top_n; both fixes are correct. Unbounded cache retention is a valid additional finding, not a false alarm; top_n severity is overstated.

**C.** Finds missing user_id in cache key and ascending top_n; both fixes are correct.

**D.** Finds missing user_id in cache key and ascending top_n; both fixes are correct.

**E.** Finds missing user_id in cache key and ascending top_n; both fixes are correct.

### r2_orders_route

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 4 | 4 | 5 | 5 | 2 | 0 | - | - |
| B | 3 | 3 | 4 | 5 | 4 | 2 | 0 | - | - |
| C | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| D | 4 | 3 | 3 | 5 | 4 | 2 | 1 | - | - |
| E | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |

**A.** Finds SQL injection and the page offset bug; invalid page validation is a real extra issue.

- **Errors / unsupported claims:** Groups page=0 with negative/NaN offsets, although 0 * 20 is 0.

- **Omissions / limitations:** The proposed status=$2 fix must also shift LIMIT/OFFSET placeholders; this is not stated.

**B.** Finds both planted bugs and correctly shifts SQL placeholders.

- **Errors / unsupported claims:** Says page=0 returns the second page; actual offset is 0, returning the first page. Zero does not yield a negative/NaN offset. Math.max(1, parseInt(...)) does not fix NaN.

**C.** Finds both bugs with parameter renumbering, correct offset and positive-integer validation.

**D.** Finds both bugs and the genuine input-validation gap. Response shape/projection changes are observable, but client breakage is not established.

- **Errors / unsupported claims:** Claims zero produces a negative/NaN offset. Claims existing clients will break without any shown clients or compatibility contract.

- **Omissions / limitations:** Status placeholder fix omits renumbering LIMIT/OFFSET; Math.max does not handle NaN.

- **False alarms:** Reports definite client breakage from the response change without a shown compatibility requirement; a conditional compatibility question would be appropriate.

**E.** Finds both planted bugs; concrete injection example, placeholder adjustment and input validation are sound.

### r3_charge_retry

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 5 | 5 | 5 | 5 | 5 | 2 | 0 | - | - |
| B | 4 | 5 | 4 | 5 | 5 | 2 | 0 | - | - |
| C | 4 | 5 | 4 | 5 | 5 | 2 | 0 | - | - |
| D | 4 | 4 | 4 | 5 | 5 | 2 | 0 | - | - |
| E | 3 | 3 | 3 | 5 | 4 | 2 | 1 | - | - |

**A.** Finds the missing await and success break; accurately distinguishes duplicate gateway calls from guaranteed duplicate charges.

**B.** Finds both bugs and later-failure risk; break is the correct fix.

- **Errors / unsupported claims:** Alternative suggestion to return immediately after gateway success would skip the required audit and ledger calls.

**C.** Finds both bugs with usable break/await fixes.

- **Errors / unsupported claims:** Alternative direct return after the gateway call skips audit and ledger. A later transient error is re-raised only on the final attempt, not every later failure.

**D.** Finds both bugs and provides correct fixes.

- **Errors / unsupported claims:** Says the loop can mask a later transient failure; the important failure mode is a final retry error turning an earlier success into an exception.

**E.** Finds both planted bugs, but adds an unjustified backoff defect.

- **Errors / unsupported claims:** Calls the 0.4s/0.8s schedule an off-by-one bug merely because another convention exists; no required schedule is supplied. Returning early after gateway success would skip audit/ledger.

- **False alarms:** Backoff exponent off-by-one is not an established defect.

### e1_retry

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 3 | 4 | 4 | 3 | - | - | - | - |
| B | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| C | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| D | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| E | 3 | 3 | 3 | 4 | 3 | - | - | - | - |

**A.** Accurate main retry matrix, four attempts, precedence, jitter and Retry-After scope; repeats code and configuration extensively.

- **Errors / unsupported claims:** Numeric citations are wrong: HTTPKIT_RETRIES is at config.py:44-45, not :38; header extraction is client.py:61, not :44. Conventional backoff indexing alone does not prove a bug.

- **Omissions / limitations:** Does not explain URLError-wrapped timeouts becoming ConnectionError and hence retrying POST, or broad OSError-to-TimeoutError mapping. Does not discuss losing custom sleep/rng when constructing the per-call policy.

**B.** Accurate main behavior and both genuine README mismatches.

- **Errors / unsupported claims:** Treats README example backoff_base=1.0 versus default 0.5 as a disagreement; an override example need not equal defaults. Calls first delay twice the documented base, although the README does not specify that first-delay contract.

- **Omissions / limitations:** Does not explain URLError-wrapped timeouts becoming ConnectionError and hence retrying POST, or broad OSError-to-TimeoutError mapping. Does not discuss losing custom sleep/rng when constructing the per-call policy.

**C.** Covers the retry matrix, attempts, config and header behavior; substantial repetition.

- **Errors / unsupported claims:** Calling conventional exponent indexing a definite bug is unsupported. Says 503 is never passed to wait: actually wait is invoked on eligible 503 responses, without its Retry-After header.

- **Omissions / limitations:** Does not explain URLError-wrapped timeouts becoming ConnectionError and hence retrying POST, or broad OSError-to-TimeoutError mapping. Does not discuss losing custom sleep/rng when constructing the per-call policy.

**D.** Main behavior and the two documentation mismatches are correct; repeats the same findings in several sections.

- **Errors / unsupported claims:** Labels the exponent an off-by-one defect based only on typical practice, without an expected schedule.

- **Omissions / limitations:** Does not explain URLError-wrapped timeouts becoming ConnectionError and hence retrying POST, or broad OSError-to-TimeoutError mapping. Does not discuss losing custom sleep/rng when constructing the per-call policy.

**E.** Main retry behavior is correct, but the extra configuration restriction is fabricated.

- **Errors / unsupported claims:** Claims retry_on_status cannot be overridden with a non-tuple without constructing proper RetrySettings. Dataclass annotations are not runtime enforcement: a list works with membership checks and this override constructor. Conventional backoff indexing is not by itself a bug.

- **Omissions / limitations:** Does not explain URLError-wrapped timeouts becoming ConnectionError and hence retrying POST, or broad OSError-to-TimeoutError mapping. Does not discuss losing custom sleep/rng when constructing the per-call policy.

### e2_log

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 3 | 4 | 4 | 3 | - | - | - | - |
| B | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| C | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| D | 4 | 4 | 4 | 4 | 3 | - | - | - | - |
| E | 4 | 3 | 4 | 4 | 3 | - | - | - | - |

**A.** Correct deploy -> gift-card error-path connection leak -> exhaustion -> 503s -> restart diagnosis, with real timestamps and useful rollback/release recommendations.

- **Errors / unsupported claims:** Asserts GC pauses and Redis slow GETs are secondary pressure from queuing/backlog. The logs establish no such causal link; these are unrelated noise in the reference scenario.

- **Omissions / limitations:** Does not cite the renewed post-restart rise from active=3 to 6 to 7 as evidence that recovery is temporary. Restart is not clearly distinguished as only temporary; the extra log-format investigation is speculative.

**B.** Correct root cause, timeline and rollback/release fix; long but useful evidence.

- **Errors / unsupported claims:** Calls one observed liveness-triggered restart a crash loop; repeated crashes are not shown. Says all listed noise occurs before and after, although the payment-config line appears only at the end.

- **Omissions / limitations:** Does not cite the renewed post-restart rise from active=3 to 6 to 7 as evidence that recovery is temporary. Does not include the final gateway alert or explicitly explain recurrence after restart.

**C.** Correct likely root cause, relevant evidence, mitigation and tests; recognizes recurrence.

- **Errors / unsupported claims:** Says pool active rises monotonically, but it drops 5->4 at 14:02:42 and 17->15 at 14:05:51. Broadens the leak to error / normal path without evidence of a normal-path leak.

- **Omissions / limitations:** Does not cite the renewed post-restart rise from active=3 to 6 to 7 as evidence that recovery is temporary.

**D.** Correct connection leak diagnosis and rollback recommendation, with accurate quoted log events.

- **Errors / unsupported claims:** Claims GC pauses are normal for the heap size; heap occupancy 71% does not establish heap size or normal GC latency. Calls the restart a crash, which is not shown.

- **Omissions / limitations:** Does not cite the renewed post-restart rise from active=3 to 6 to 7 as evidence that recovery is temporary. Does not clearly explain that restarting without fixing the leak only buys time.

**E.** Correct root cause and explicitly temporary restart mitigation; sound release/test recommendations.

- **Errors / unsupported claims:** Asserts GC/Redis delays are load-induced secondary effects without evidence. Says active count is monotonic despite observed decreases. Restart alone does not prove the precise code-path cause, although the combined leak warnings strongly support it.

- **Omissions / limitations:** Does not cite the renewed post-restart rise from active=3 to 6 to 7 as evidence that recovery is temporary.

### e3_varint

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 3 | 2 | 3 | 4 | 3 | - | - | - | - |
| B | 3 | 3 | 3 | 4 | 3 | - | - | - | - |
| C | 3 | 2 | 3 | 4 | 3 | - | - | - | - |
| D | 2 | 2 | 2 | 3 | 3 | - | - | - | - |
| E | 4 | 4 | 4 | 4 | 4 | - | - | - | - |

**A.** Core varint mechanics, worked example and 70-bit/signed range are correct.

- **Errors / unsupported claims:** Claims protobuf parsers reject all non-minimal encodings; this blanket restriction is false. Calls FF 01 a non-canonical example although it is the minimal encoding of 255. Says any extra zero-payload continuation bytes change the value, contradicting its own zero-padding example. Initially conflates all protobuf signed ints with ZigZag. Calling the byte limit one byte early is misleading: byte 10 with continuation already proves the limit is exceeded.

- **Omissions / limitations:** Does not explain lazy exceptions after previously yielded values. Does not clearly explain ordinary protobuf int32/int64 negative two's-complement values versus sint ZigZag.

**B.** Accurate decoder mechanics, byte-limit placement and range; correctly identifies sint ZigZag.

- **Errors / unsupported claims:** Claims protobuf universally requires minimal encoding and strict parsers must reject padding. No such universal compatibility rule is established.

- **Omissions / limitations:** Does not explain lazy exceptions after previously yielded values. Does not clearly explain ordinary protobuf int32/int64 negative two's-complement values versus sint ZigZag.

**C.** Correct arithmetic example and exact 70-bit and ZigZag limits.

- **Errors / unsupported claims:** Says strict parsing must reject leading 0x80: 80 01 is a valid minimal encoding of 128. Claims protobuf universally requires shortest form. Conflates overflow with non-canonical encoding; a minimally encoded value can exceed 64 bits. Says an 11th continuation is rejected, but the error occurs upon the 10th continuation.

- **Omissions / limitations:** Does not explain lazy exceptions after previously yielded values. Does not clearly explain ordinary protobuf int32/int64 negative two's-complement values versus sint ZigZag.

**D.** Recognizes basic encoding and correct numeric limits, but multiple decoding examples and pseudocode are wrong.

- **Errors / unsupported claims:** Claims 81 00 decodes to 0; it decodes to 1. Treats 01 80 01 as one non-minimal value; the stream yields 1 and 128. Pseudocode yields before ZigZag, unlike the source. Presents ZigZag encoding direction as decoding. Blanket canonical-minimal protobuf requirement is false.

- **Omissions / limitations:** Does not explain lazy exceptions after previously yielded values. Does not clearly explain ordinary protobuf int32/int64 negative two's-complement values versus sint ZigZag.

**E.** Best varint answer: accurate examples, permissiveness and exact unsigned range.

- **Errors / unsupported claims:** Suggests max_bytes=5/10 plus rejecting non-canonical forms suffices for 32/64-bit compatibility; those limits still allow 35/70 bits and need explicit overflow checks. Negative ordinary int32 values may occupy 10 bytes.

- **Omissions / limitations:** Does not explain lazy exceptions after previously yielded values. Does not clearly explain ordinary protobuf int32/int64 negative two's-complement values versus sint ZigZag.

### e4_design

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 4 | 3 | 3 | 3 | - | - | - | - |
| B | 3 | 3 | 3 | 3 | 4 | - | - | - | - |
| C | 4 | 3 | 3 | 3 | 4 | - | - | - | - |
| D | 4 | 4 | 4 | 4 | 4 | - | - | - | - |
| E | 4 | 4 | 3 | 3 | 4 | - | - | - | - |

**A.** Good atomic-claim SQL, heartbeat/reclaim, index and retention proposals; approximately 342 whitespace words exceed the requested ~300.

- **Errors / unsupported claims:** Retry fix increments attempts on failure as well as on claim, double-counting failed executions.

- **Omissions / limitations:** Misses external side-effect success followed by crash before done, and the need for handler idempotency. Does not discuss stale updated_at, metrics or committing the claim before the handler.

**B.** Covers claim race, recovery, index/archive and retry limits in about 286 words.

- **Errors / unsupported claims:** Says attempts=attempts+1 is non-atomic / a lost-update problem. The SQL increment is atomic; the separate claim is what is unsafe. Predicts thousands of queued retries without workload evidence.

- **Omissions / limitations:** Mentions already-succeeded jobs being replayed but gives no idempotency fix or complete external-side-effect crash explanation. No observability or updated_at maintenance analysis.

**C.** Covers atomic claim, heartbeat, index, retention, retry cap and metrics in about 319 words.

- **Errors / unsupported claims:** Calls retained done rows dead tuples; retained rows are live tuples. Uses peak 200 jobs/s as a sustained growth premise; >17M/month is an imprecise lower bound, not a supported monthly forecast.

- **Omissions / limitations:** Misses external API side-effect crash window and idempotent handlers. No updated_at maintenance or short-transaction discussion.

**D.** Most useful design critique: claim race, external side-effect duplication/idempotency, bounded retries, index and retention in about 297 words.

- **Errors / unsupported claims:** Describes attempts increment as occurring on exception; the proposal increments on claim.

- **Omissions / limitations:** Automatic fixed-age reclaim has no heartbeat/fencing, risking duplicate execution of a still-running worker. Does not call out stale updated_at or metrics; no explicit commit-before-handler guidance.

**E.** Good atomic claim, heartbeat, retention/index and retry-limit coverage in about 313 words.

- **Errors / unsupported claims:** Predicts autovacuum falling behind at the stated peak as certain, without measured capacity.

- **Omissions / limitations:** Misses external side-effect crash window and idempotency; no jitter/cap in suggested backoff. Does not explicitly identify updated_at maintenance for completion or add observability.

### hr1_payout_retry

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 3 | 3 | 4 | 5 | 4 | 2 | 1 | - | - |
| B | 4 | 3 | 4 | 5 | 5 | 2 | 0 | - | - |
| C | 4 | 4 | 5 | 5 | 5 | 2 | 0 | - | - |
| D | 4 | 3 | 4 | 5 | 5 | 2 | 0 | - | - |
| E | 4 | 3 | 4 | 5 | 5 | 2 | 0 | - | - |

**A.** Finds both the changing-idempotency-key and float-conversion bugs; the proposed stable key and Decimal fixes are sound.

- **Errors / unsupported claims:** Incorrect numerical example: int(float("129.99") * 100) is 12999, not 12998; use "4.35" -> 434 or "0.29" -> 28. Assumes ProviderError includes permanent validation/business errors; the provider implementation/error hierarchy is not shown.

- **False alarms:** Definite claim that ProviderError includes non-transient errors requiring a different retry policy is unsupported by shown sources.

**B.** Finds both the changing-idempotency-key and float-conversion bugs; the proposed stable key and Decimal fixes are sound.

- **Errors / unsupported claims:** Incorrect numerical example: int(float("129.99") * 100) is 12999, not 12998; use "4.35" -> 434 or "0.29" -> 28.

**C.** Finds both bugs and supplies a correct 0.29 -> 28 example and Decimal solution; conditional retry-policy note is not counted as a separate defect.

- **Errors / unsupported claims:** Under/over-payment wording is broader than demonstrated; positive two-decimal cent values illustrate underpayment. Permanent ProviderError semantics are unknown; the note is qualified as conditional advice.

**D.** Finds both the changing-idempotency-key and float-conversion bugs; the proposed stable key and Decimal fixes are sound.

- **Errors / unsupported claims:** Incorrect numerical example: int(float("129.99") * 100) is 12999, not 12998; use "4.35" -> 434 or "0.29" -> 28.

**E.** Finds both the changing-idempotency-key and float-conversion bugs; the proposed stable key and Decimal fixes are sound.

- **Errors / unsupported claims:** Incorrect numerical example: int(float("129.99") * 100) is 12999, not 12998; use "4.35" -> 434 or "0.29" -> 28.

### hr2_webhook_credit

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 5 | 5 | 4 | 5 | 3 | 2 | 0 | - | - |
| B | 3 | 3 | 3 | 5 | 2 | 2 | 2 | - | - |
| C | 4 | 4 | 4 | 5 | 3 | 2 | 1 | - | - |
| D | 4 | 4 | 4 | 5 | 3 | 2 | 0 | - | - |
| E | 4 | 4 | 4 | 5 | 3 | 2 | 0 | - | - |

**A.** Finds both bugs with correct atomic insertion and explicit event-type fixes. Item 3 repeats the crash window already included in item 1; counts as two planted bugs, not three.

**B.** Finds both planted bugs, but repeats deduplication and adds unsupported business/contract findings.

- **Errors / unsupported claims:** Claims a unique violation means no event-id record exists and a later retry reapplies; a duplicate-key conflict means the competing delivery already recorded that id. A general DB failure/crash still creates the real missing-marker window. Negative reversal balances are not prohibited by any shown business rule. Exact-string-dependent callers are not shown.

- **False alarms:** Negative balance on reversal is reported as a security defect without a nonnegative-balance contract. Claims caller breakage from credited -> applied without any shown callers/compatibility requirement.

**C.** Finds both bugs; item 3 duplicates deduplication, and item 4 assumes unseen callers.

- **Errors / unsupported claims:** A unique-constraint conflict from a race implies an event marker exists, so it does not itself cause a subsequent replay. Claims exact-string-dependent callers break without showing them.

- **False alarms:** Reports definite caller breakage from the return-string change without a shown contract.

**D.** Finds both bugs and valid fixes; repeats the same non-atomic-recording issue.

- **Errors / unsupported claims:** Conflates add failure/race with a missing marker: a unique conflict from a race implies a marker exists. Independent insert failure/crash remains a real replay window.

**E.** Finds both bugs and gives correct fixes; item 3 repeats item 1.

- **Errors / unsupported claims:** Says an insert failure due to a race leaves no idempotency record and allows replay; for a unique-key conflict the competing marker exists. A general DB error can still create the stated window.

### he1_cancel

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 3 | 1 | 3 | 4 | 2 | - | - | 2 | 0 |
| B | 4 | 3 | 4 | 4 | 2 | - | - | 1 | 0 |
| C | 3 | 2 | 3 | 4 | 2 | - | - | 2 | 0 |
| D | 2 | 1 | 2 | 4 | 2 | - | - | 4 | 0 |
| E | 3 | 3 | 3 | 4 | 2 | - | - | 1 | 0 |

**A.** Detailed and mostly correctly cited flow; catches full-quantity restock, reservation omission and mutation-before-payment risk. Two final bug claims contradict the shown guards.

- **Errors / unsupported claims:** Claims SHIPPED orders still restock/notify, then acknowledges the earlier conflict blocks this. Claims no guard against double partial cancellation, then cites the guard that rejects it.

- **Omissions / limitations:** Does not fully discuss payment-before-save retry/idempotency risk and notification failure after save. Does not flag reason=null slicing failure; several normal behaviors are listed as risks.

- **Citation audit:** wrong: `shop/refund_calc.py:25` — Shipping paragraph alleges restocking/notifying an already SHIPPED order; refund condition does not support this and orders.py:25-26 blocks it.; wrong: `shop/orders.py:23` — No guard against double cancellation after partial cancel.

**B.** Accurate full flow and main inventory defect. Refund rounding interpretation is reversed/ambiguous; lists benign separate status checks as risks.

- **Errors / unsupported claims:** Describes floor coupon share as potentially under-refunding coupon. Flooring the amount subtracted increases net refund; it does not under-refund the customer.

- **Omissions / limitations:** Does not fully discuss payment-before-save retry/idempotency risk and notification failure after save. Does not flag reason=null slicing failure; several normal behaviors are listed as risks.

- **Citation audit:** wrong: `shop/refund_calc.py:22` — Coupon floor division described as under-refunding instead of reducing the discount deduction.

**C.** Accurate full trace and inventory bug; lengthy restatement with speculative/benign risk items.

- **Errors / unsupported claims:** Says remainder discount cents are never refunded/can accumulate; flooring coupon_share instead makes net refund slightly larger. A separate notification summary cites mail/template lines for the warehouse publish claim.

- **Omissions / limitations:** Does not fully discuss payment-before-save retry/idempotency risk and notification failure after save. Does not flag reason=null slicing failure; several normal behaviors are listed as risks.

- **Citation audit:** wrong: `shop/refund_calc.py:22` — Discount floor division said to lose refund cents.; wrong: `shop/notify.py:12-14` — Summary claims cancel_pick publication using lines that only select/send the email template; warehouse publish is at :8-10.

**D.** Main trace is correct, but the risk section invents several defects directly contradicted by its citations.

- **Errors / unsupported claims:** Claims coupon rounding under-refunds; flooring the discount deduction increases refund. Claims shipping can be refunded for partially shipped lines despite all(shipped_qty==0). Calls Enum identity comparison fragile; normal Python Enum members are singletons. Says refund is issued without payment_id despite the explicit guard. States reserved stock definitely remains, although reservation lifecycle is not shown.

- **Omissions / limitations:** Does not fully discuss payment-before-save retry/idempotency risk and notification failure after save. Does not flag reason=null slicing failure; several normal behaviors are listed as risks.

- **Citation audit:** wrong: `shop/refund_calc.py:22` — Coupon floor causes under-refund.; wrong: `shop/refund_calc.py:25` — Shipping refund while a line is partially shipped.; wrong: `shop/orders.py:25` — Enum is comparison claimed as a defect.; wrong: `shop/orders.py:33` — Payment refund issued with no payment_id.

**E.** Main trace and over-restock finding are correct; mutation-before-payment risk is identified. Repeats inventory defect and treats intended behavior as risk.

- **Errors / unsupported claims:** Explicitly says floor coupon share potentially under-refunds the customer; it reduces discount deduction and therefore increases net refund. Claims reserved stock is never released without showing its broader lifecycle.

- **Omissions / limitations:** Does not fully discuss payment-before-save retry/idempotency risk and notification failure after save. Does not flag reason=null slicing failure; several normal behaviors are listed as risks.

- **Citation audit:** wrong: `shop/refund_calc.py:22` — Floor coupon share under-refunds customer.

### he2_timeouts

| Label | C | G | U | Co | Cn | Planted | False alarms | Wrong cites | Hallucinated cites |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 3 | 4 | 4 | 4 | - | 0 | 1 | 0 |
| B | 4 | 3 | 4 | 4 | 4 | - | 0 | 1 | 0 |
| C | 5 | 5 | 5 | 4 | 4 | - | 0 | 0 | 0 |
| D | 4 | 3 | 4 | 4 | 3 | - | 0 | 1 | 0 |
| E | 4 | 3 | 4 | 4 | 4 | - | 0 | 1 | 0 |

**A.** Identifies all eight U groups and all six S groups with correct classifications, but misses one operation and mislabels a call site.

- **Errors / unsupported claims:** Labels sync.py:15 as list_issues connect; that line calls fetch_all(mirrors,...), while list_issues is called at sync.py:13.

- **Omissions / limitations:** Does not explicitly explain Redis sendall/recv inheriting the 1.5-second socket timeout. Does not distinguish socket-operation inactivity bounds from total wall-clock deadlines. Omits post_metrics writer.drain() at fetch.py:42. Does not give the numeric 5-second httpx default.

- **Citation audit:** wrong: `svc/workers/sync.py:15` — list_issues connect call site is assigned to the mirrors fetch call.

- **Recall:** 8/8 U groups, 6/6 S groups; 0 bounded-as-unbounded false alarms. Group recall does not imply every operation within the group was listed.

**B.** Correct U1-U8 and S1-S6 classification and timeout origins; drain behavior is correct but cited to the wrong line.

- **Omissions / limitations:** Does not explicitly explain Redis sendall/recv inheriting the 1.5-second socket timeout. Does not distinguish socket-operation inactivity bounds from total wall-clock deadlines. Does not explicitly list SMTP recv at fetch.py:17 or numeric 5-second httpx default.

- **Citation audit:** wrong: `svc/workers/fetch.py:40` — The paragraph also claims writer.drain is unbounded, but its only fetch citation is open_connection; drain is at :42.

- **Recall:** 8/8 U groups, 6/6 S groups; 0 bounded-as-unbounded false alarms. Group recall does not imply every operation within the group was listed.

**C.** Strongest timeout answer: all U/S groups, SMTP recv, archive iter_content, drain at its actual line and the numeric httpx default are covered; no bad citations.

- **Omissions / limitations:** Does not explicitly explain Redis sendall/recv inheriting the 1.5-second socket timeout. Does not distinguish socket-operation inactivity bounds from total wall-clock deadlines.

- **Recall:** 8/8 U groups, 6/6 S groups; 0 bounded-as-unbounded false alarms. Group recall does not imply every operation within the group was listed.

**D.** Correct U/S classifications, but confuses omitted timeouts and explicit None and misses drain.

- **Errors / unsupported claims:** Invents socket.create_connection(host,port,timeout=None) as the relevant default/signature and says explicit None uses getdefaulttimeout. The shown call passes an address tuple; omitted timeout uses the global default, whereas explicit None means blocking. Describes urllib explicit None as a library-default fallback rather than explicitly disabling timeout.

- **Omissions / limitations:** Does not explicitly explain Redis sendall/recv inheriting the 1.5-second socket timeout. Does not distinguish socket-operation inactivity bounds from total wall-clock deadlines. Omits post_metrics drain at fetch.py:42 and numeric httpx default.

- **Citation audit:** wrong: `svc/workers/fetch.py:15` — Cited omitted-timeout call does not support invented signature or explicit-None/global-default equivalence.

- **Recall:** 8/8 U groups, 6/6 S groups; 0 bounded-as-unbounded false alarms. Group recall does not imply every operation within the group was listed.

**E.** Correct U/S classifications, config trace and numeric httpx default; drain is described but cited only to connect.

- **Omissions / limitations:** Does not explicitly explain Redis sendall/recv inheriting the 1.5-second socket timeout. Does not distinguish socket-operation inactivity bounds from total wall-clock deadlines. Does not explicitly list SMTP recv at fetch.py:17.

- **Citation audit:** wrong: `svc/workers/fetch.py:40` — writer.drain claim has only the :40 connection citation; drain is at :42.

- **Recall:** 8/8 U groups, 6/6 S groups; 0 bounded-as-unbounded false alarms. Group recall does not imply every operation within the group was listed.

## Notable errors across answers

- All 25 review answers found both planted bugs (50/50 possible detections), but this does not imply all accompanying claims were correct.
- Payout A/B/D/E invented the same wrong 129.99 -> 12998 example; the actual result is 12999. C used the valid 0.29 -> 28 example.
- Varint D says 81 00 decodes to zero (actual 1), confuses a two-value stream with a single encoding, and puts yield before ZigZag. A-D overstate protobuf canonical-encoding requirements; C would reject valid 80 01. All omit the important late-generator-error explanation.
- Cancellation D invents shipping refunds after partial shipment, refunds without payment_id, and an Enum identity bug. A simultaneously asserts and quotes away two missing-guard bugs. B-E misinterpret coupon-floor rounding; the floor reduces the discount deducted, increasing the refund.
- Webhook B adds unsupported negative-balance and caller-contract defects. Several answers incorrectly claim a duplicate-key conflict means no event marker exists; the separate crash/DB-error window is real.
- Retry E invents a restriction on list-valued retry_on_status. Design B incorrectly calls SQL attempts=attempts+1 non-atomic. Most design answers miss the external-side-effect crash window/idempotency fix.
- Log A/E invent a load-induced explanation for GC/Redis noise; C/E repeat a false monotonic-pool claim. All miss citing the renewed rise to active=7 after restart.
- Timeout A cites the mirrors fetch line as list_issues; B/E cite connect for drain. D confuses explicit None with omitted timeout. C has the strongest source tracing, though no answer explicitly covers Redis send/recv timeout inheritance in full.

## JSON layout

`GRADES.json` is a direct mapping `label -> task_id -> scores, counters, notes, omissions, unsupported claims, citation issues`. Null means not applicable, not zero. Per-label means above are computed from the integer per-task scores. The JSON contains exactly five labels and 55 per-task records.
