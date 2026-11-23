# PLATON readiness and final official PDF

## Diagnose execution before missing files

In Windows, launching a GUI-linked executable from a shell can return before calculation/output finishes. Do not inspect an early zero-byte `.chk` then conclude that rules are missing or start another job in the same directory. Use the Python process-owning runner in a fresh directory. It waits for complete `.chk` and `.ckf`, the CheckCIF/CheckFCF markers, a valid alert footer/count parse and stable file sizes. It terminates only its own remaining process after complete reports; a failure preserves the logs and incomplete status.

An external `check.def` is not required for modern embedded-rule builds. Read the actual PLATON/check.def version from the generated report and record the executable hash and relevant environment/external-rule context. A changed rule context invalidates new local cache records. A missing external file alone is not an error. Only an explicit missing-file diagnostic can be classified that way; crashes, timeouts, invalid input and incomplete output have different causes.

```text
python cairystal.py platon-check --cif CURRENT.cif --output NEW_LOCAL_DIRECTORY
python cairystal.py platon-check --cif CURRENT.cif --fcf PAIRED.fcf --output NEW_LOCAL_DIRECTORY
```

The local runner never uploads. Without an FCF it requires either embedded calculated/observed reflection data or embedded SHELX HKL and RES; native reconstruction is labelled as such. A local rule version may differ from IUCr's version. Keep both alert sets and their versions; never overwrite one set with the other to make it appear that all warnings disappeared.

## Obtain the PDF, not merely a response page

The maintained `iucr_validation.py` explicitly requests `outputtype=PDF` and `validtype=checkcif_with_hkl`. The submission response is normally HTML containing the PDF and FCF-detail links. Save that HTML as `response.html`, follow the validated official links, then save the genuine `%PDF` bytes as `IUCr_checkCIF.pdf`. Validate page readability, alert counts, syntax and structure-factor confirmation, and associate the report with the immutable submitted CIF hash.

Each report GET has up to three attempts (at most 60 seconds configured socket timeout per attempt, then short backoff). Retry temporary report errors only; a rejected request such as HTTP 403 stops. PDF download is committed and hashed before FCF-detail retrieval. If the latter fails, preserve the PDF and use its checked hash on recovery, without another PDF GET. Retain incomplete HTML/binary responses separately for diagnosis. Never describe a broken/HTML response as a PDF or report success before required artifacts validate.

No automatic re-POST after an uncertain submission. `recover-checkcif` only retrieves the already-returned report URLs; if no response links exist, record the uncertainty for review. Remote service outages cannot be made impossible, but missing PDF or unverified output must never be silently marked complete.

## Primary documentation

- [PLATON for Windows distribution notes](https://www.chem.gla.ac.uk/~louis/software/platon/) explain embedded check.def in current Windows builds.
- [PLATON validation manual](https://platonsoft.nl/platon/pl000601.html) documents `-u` / `-U` validation.
- [IUCr official form](https://checkcif.iucr.org/) provides PDF and structure-factor validation options.

This is generic execution guidance, not a crystallographic reference model. Do not load maintenance crystal fixtures during blind solving.
