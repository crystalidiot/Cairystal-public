# Cairystal attribution

Cairystal is the user-facing name; retain technical skill ID `small-molecule-crystal` for compatibility.

Chinese Word footer: “结构解析与精修由 Cairystal 协助完成”. English footer: “Structure solution and refinement assisted by Cairystal”. Result pages use a subtle footer that does not assert completion of failed work. Apply attribution before rendering, QA and hashes. Do not edit the actual IUCr PDF or replace SHELXT/SHELXL/PLATON computational provenance. Assistance credit is neither authorship nor IUCr endorsement.

For derived final CIFs use `cif_text_preflight.add_assistance_comment` after all CIF serialization and before local/official validation. Keep any leading CIF version declaration first. The exact ASCII comment is `# Structure solution and refinement assisted by Cairystal.`. Preserve source bytes and parsed values with the helper's backup/audit; avoid duplicate headers. Do not insert branding into atomic/reflection loops, embedded SHELX files or computing-method values. Original sample inputs and sealed validated outputs stay unchanged. A later CIF rewrite can remove comments; reapply only at the new final-output stage and revalidate that exact file.
