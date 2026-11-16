# Chester.Tech Rocket T830 OTA

Signed OTA updates for the **Misecte M620-N** on board
`mediatek,evb6990_cpe_mt76_emmc`.

This repository starts with release tooling and a firmware overlay. It has no
stable release. The existing customized M620N01R06 BIN is **not hardware boot
tested** and is not advertised to devices as a stable OTA update.

**Live target review: DO NOT FLASH the earlier candidates.** The vendor BIN
contains a different bootloader, Ethernet PHY module and Ethernet firmware from
the target at `192.168.100.1`. Its updater also clones boot areas between slots,
and a late-boot service can synchronize the new slot over the previous slot.
Matching board IDs and A/B partitions do not establish a safe rollback path.
The final image must use a verified matching base, resolve rootfs authentication,
and have a tested recovery path before publication as stable. The new UI changes
below are source-only in this draft; they have not been installed on the router.

## Client controls

Under **System → System Update**, the page has the K43P-style saved toggles:

- **Retain data**: on by default. Preserves router settings; off passes `-n` to
  vendor sysupgrade and returns configuration to defaults. This is not a full
  backup of every partition or a promise to retain installed applications.
- **Auto update**: off by default. When enabled, cron checks at minute 19 every
  six hours and installs only a newer signed, hardware-tested stable release.
  Scheduled updates honor the same retain-data preference. Disabling automatic
  updates during a download cancels installation before flashing.

Manual updates still have a separate install confirmation. The page saves both
preferences, offers **Check for updates**, shows job status, and reconnects after
installation. An updater worker handles downloads outside the web RPC timeout.
Preferences use the same UCI keys as the K43P: `chester.update.keep_settings`
and `chester.update.auto`. Defaults preserve saved preferences and existing cron
jobs rather than resetting them during an upgrade.

## Update flow

1. Build an image containing `firmware-overlay/`, including its public key and a
   monotonically increasing `etc/chester-ota/installed-sequence`.
2. Test that exact BIN on the supported hardware and confirm recovery works.
3. Prepare release assets locally with your private Ed25519 signing key.
4. Upload the BIN, `ota.json`, `ota.json.sig` and `SHA256SUMS.txt` to a GitHub
   Release whose tag matches `v<version>`. Keep candidates in drafts/prereleases.
5. A device checks the latest published stable release and verifies its signature,
   model, board and sequence. Installation needs manual confirmation or the
   customer's saved automatic-update opt-in.

```sh
chester-ota check
chester-ota install --confirm
```

The client requires wget-ssl with a working CA bundle, OpenSSL with Ed25519,
jq, ubus, UCI, cron, start-stop-daemon, sha256sum, cmp, tar, unsquashfs and the vendor sysupgrade implementation.
The audited vendor filesystem contains these tools. The scheduled entry exits
without network access until Auto update is enabled. No GitHub token is stored
on the device.

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

Run local tests with `python3 -m unittest discover -s tests -v` and
`node tests/test_view.js`. Installation tests always replace sysupgrade with a
stub and do not flash hardware.
