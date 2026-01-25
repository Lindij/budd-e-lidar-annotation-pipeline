# Project Checklist

## Data + Pipeline
- [ ] Add a script to merge split Segments.ai samples back into one per rosbag (keep on backlog).
- [ ] Validate that all new rosbags follow `_YYYY-MM-DD-HH-MM-SS.bag` naming.
- [ ] Confirm `data/interim/<bag_id>_pcd` and `data/processed/<bag_id>/<model>` naming for every bag.

## Configs and Scripts
- [x] Clean `configs/upload_tracks/` and move legacy configs to `configs/upload_tracks/legacy/`.
- [ ] Remove or populate empty `configs/pcdet/` if unused.
- [ ] Keep a single default upload config for the current pipeline.

## Documentation
- [x] Update `README.md` to match current layout and commands.
- [x] Add parallel setup doc (`docs/setup_parallel.md`).
