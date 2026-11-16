# Chester.Tech Rocket T830 OTA

Signed, manually initiated OTA updates for the **Misecte M620-N** on board
`mediatek,evb6990_cpe_mt76_emmc`.

This repository starts with release tooling and a firmware overlay. It has no
stable release. The existing customized M620N01R06 BIN is **not hardware boot
tested** and is not advertised to devices as a stable OTA update.

## Update flow

1. Build an image containing `firmware-overlay/`, including its public key and a
   monotonically increasing `etc/chester-ota/installed-sequence`.
2. Test that exact BIN on the supported hardware and confirm recovery works.
3. Prepare release assets locally with your private Ed25519 signing key.
4. Upload the BIN, `ota.json`, `ota.json.sig` and `SHA256SUMS.txt` to a GitHub
   Release whose tag matches `v<version>`. Keep candidates in drafts/prereleases.
5. A device checks the latest published stable release, verifies its signature,
   model, board and sequence, and installs only after an explicit root command.

```sh
chester-ota check
chester-ota install --confirm
```

The client requires wget-ssl with a working CA bundle, OpenSSL with Ed25519,
jq, ubus, sha256sum, cmp, tar, unsquashfs and the vendor sysupgrade implementation.
The audited vendor filesystem contains these tools. No cron job, background
installer, GitHub token or unattended flashing is added.

This client is a proposed overlay. It has not been installed on or tested against
the live router. Existing firmware needs an initial supported manual upgrade to
gain the OTA client. GitHub repository creation alone does not enable OTA.

## Prepare a candidate

```sh
python3 tools/prepare_release.py \
  --image /path/to/firmware.bin \
  --private-key /offline/location/release-signing.pem \
  --output dist/v2026.11.15.1 \
  --version 2026.11.15.1 --sequence 1
```

Candidates are signed but marked `candidate`/`boot_tested=false`; the device
refuses to install them. Add `--boot-tested` only after testing that exact image
on hardware. The image must embed the same sequence and public key or the client
will reject installation. New releases use a higher version AND sequence.

## Signing key

Only the public key belongs in this repository. The private key is generated and
stored locally, outside the repository. Keep an offline backup. Do not put it in
GitHub Actions secrets or firmware. Losing it prevents updates to devices that
trust its public key; replacing it requires a separate supported trust migration.

The OTA key is independent of the vendor keys found in the firmware audit. Those
vendor credentials are not used by this project. Firmware secure boot is a
separate requirement and is not bypassed by the OTA signature.

## Known firmware risks

The prior audit found a vendor FOTA signing key shipped with its matching
certificate, a guest login with wildcard ACLs, disabled FOTA checking, weak
defaults and a startup-enabled LwM2M client. These require separate remediation.
The new OTA transport does not harden those unrelated services or prove the
firmware is safe to boot. No BIN or vendor private key is committed here.

Run local tooling tests with `python3 -m unittest discover -s tests -v`.
