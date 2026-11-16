# T830 live compatibility review

Reviewed read-only on 2026-11-16. **Earlier English/OTA candidates are not cleared
for flashing.** No firmware, boot-slot or persistent configuration writes were
made to the target, and it was not rebooted.

## Confirmed matches

- Misecte M620-N, MediaTek MT6990 / T830; board
  `mediatek,evb6990_cpe_mt76_emmc`, also compatible `misectel,m620n`.
- OpenWrt 23.05.6, Linux 5.15.167, ARM64, 44 eMMC partitions.
- 32 MiB boot slots and 1 GiB rootfs slots; candidate components fit.
- The active and candidate Android boot device-tree blobs are byte-identical:
  `355498caddebbd9c60fd2ad3711c6a68a6d9088cb8b7caf71e7dc24aed543eae`.
- Kernel differences are limited to the embedded IKCONFIG block and GNU build
  ID. The configuration differs in bridge firewall and USB serial selections.
- Board initialization and shared upgrade scripts match the active ROM.

## Flash-clearance blockers

1. **Different bootloader:** the vendor `lk-verified.img` is not the active LK.
   Its first MediaTek payload is 328,208 bytes; the live payload is 329,848.
   The earlier candidates include this replacement although language changes
   do not require it.
2. **Different Ethernet components:** `air_en8811h.ko`, `nf_tables.ko`,
   `EthMD32.DSP.bin` and `EthMD32.dm.bin` differ. Matching board names do not
   rule out Ethernet regressions.
3. **A/B does not establish safe rollback:** `clone_non_update_images` copies
   non-updated boot components, including the inactive eMMC preloader area.
   The late-boot `zmtk_boot_done` service calls `ab_image_sync` and can overwrite
   the previous slot after startup. Omitting a bootloader archive member does
   not make this updater boot-area-write-free.
4. **Authentication unresolved:** rootfs-signature and secure-boot machinery
   exists, but exported live data did not establish modified-rootfs acceptance.
   `ql_sec_fota=0` only skips one userspace check; it does not establish that
   hardware secure boot is off.
5. **Recovery untested:** no vendor recovery process, serial/boot-ROM path,
   automatic fallback, power-failure test, or complete recovery backup has been
   verified.

The next image needs a verified matching base, deliberate boot-area/slot
handling, resolved signing requirements, backups and a tested recovery path.
Keep releases as drafts/candidates until the exact final image is hardware
tested. The GUI and scheduler code in this PR have passed isolated tests but
are not installed on the live target.
