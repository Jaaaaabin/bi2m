# BCF 3.0 schemas (upstream copies, unedited)

`visinfo.xsd` and `shared-types.xsd` are the buildingSMART BCF-XML 3.0
viewpoint schemas, copied on 2026-10-21 from
https://raw.githubusercontent.com/buildingSMART/BCF-XML/release_3_0/Schemas/
(sha256 `0855bc00…` and `93d20dfc…`). `views.py` validates the viewer's
`.bcfv` export against them with `xmllint --schema` when it is on PATH
(`conda`'s libxml2 ships one); without it the harness checks the element
order itself and says so.
