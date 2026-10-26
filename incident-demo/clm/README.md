# CLM

CLM replaces Jev. The orchestrator posts one decision question to
`CLM_BASE_URL/v1/systemone` with model `clm-latest` and no API key.
It does not call Jev.

CLM runs inside this organization. It does not run on a machine outside
the organization.

The server image is `CLM_IMAGE` in `BLANKS.md`. `apply.py` skips
`clm.yaml` when that variable is empty. The image and the encoder
weights are not in this tree.
