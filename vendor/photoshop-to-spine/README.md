# Official PhotoshopToSpine exporter

Upstream: <https://github.com/EsotericSoftware/spine-scripts/tree/master/photoshop>

Pinned revision: `69c429295b5b19f66f959ad2ac644d40a14121e5`

Script version: `7.42`

`PhotoshopToSpine.jsx` is stored unchanged. Its embedded copyright notice and the upstream `LICENSE` must be retained in source and packaged distributions. This project is an independent integration and is not endorsed by Esoteric Software.

The Python adapter creates a temporary script at runtime: it removes the final settings-dialog invocation, supplies export settings, replaces alerts with exceptions, checks image paths before writing, disables progress windows, optionally changes the private copy's ruler origin, and restores Photoshop document state after processing. The official layer/tag/rendering implementation is retained.

Updating the upstream revision requires reviewing these integration points and rerunning actual Photoshop/Spine conversion checks.
