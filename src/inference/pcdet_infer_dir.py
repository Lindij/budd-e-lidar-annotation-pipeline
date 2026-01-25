#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

from pcdet.config import cfg, cfg_from_yaml_file
from pcdet.models import build_network, load_data_to_gpu
from pcdet.utils import common_utils
from pcdet.datasets import DatasetTemplate


class DemoDataset(DatasetTemplate):
    def __init__(self, dataset_cfg, class_names, root_path, ext):
        super().__init__(dataset_cfg=dataset_cfg, class_names=class_names, training=False, root_path=root_path)
        self.root_path = Path(root_path)
        self.ext = ext
        if self.root_path.is_dir():
            self.sample_file_list = sorted(self.root_path.glob(f"*{self.ext}"))
        else:
            self.sample_file_list = [self.root_path]

    def __len__(self):
        return len(self.sample_file_list)

    def __getitem__(self, index):
        path = self.sample_file_list[index]
        if self.ext == ".bin":
            points = np.fromfile(path, dtype=np.float32).reshape(-1, 4)
        elif self.ext == ".npy":
            points = np.load(path)
        else:
            raise NotImplementedError(f"Unsupported ext {self.ext}")

        input_dict = {
            "points": points,
            "frame_id": index,
        }
        return self.prepare_data(data_dict=input_dict)


def parse_args():
    parser = argparse.ArgumentParser(description="Run OpenPCDet inference on a directory of point clouds")
    parser.add_argument("--cfg-file", required=True, help="Model config yaml")
    parser.add_argument("--ckpt", required=True, help="Path to pretrained checkpoint")
    parser.add_argument("--data-path", required=True, help="Point cloud file or directory")
    parser.add_argument("--ext", default=".bin", help="Point cloud extension (.bin or .npy)")
    parser.add_argument("--out", required=True, help="Output JSONL file")
    parser.add_argument("--start-index", type=int, default=0, help="Start frame index")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames to process (0 = all)")
    parser.add_argument("--log-interval", type=int, default=50, help="Log every N frames")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg_path = Path(args.cfg_file).resolve()
    data_path = Path(args.data_path).resolve()
    ckpt_path = Path(args.ckpt).resolve()
    out_path = Path(args.out).resolve()
    tools_dir = cfg_path.parents[2]
    os.chdir(str(tools_dir))
    cfg_from_yaml_file(str(cfg_path.relative_to(tools_dir)), cfg)

    logger = common_utils.create_logger()
    dataset = DemoDataset(cfg.DATA_CONFIG, cfg.CLASS_NAMES, data_path, args.ext)
    logger.info(f"Total samples: {len(dataset)}")

    model = build_network(model_cfg=cfg.MODEL, num_class=len(cfg.CLASS_NAMES), dataset=dataset)
    model.load_params_from_file(filename=str(ckpt_path), logger=logger, to_cpu=True)
    model.cuda()
    model.eval()

    out_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if args.start_index > 0 else "w"
    with torch.no_grad(), out_path.open(mode) as f:
        processed = 0
        for idx, data_dict in enumerate(dataset):
            if idx < args.start_index:
                continue
            if args.max_frames and processed >= args.max_frames:
                break
            data_dict = dataset.collate_batch([data_dict])
            load_data_to_gpu(data_dict)
            pred_dicts, _ = model.forward(data_dict)

            pred = pred_dicts[0]
            boxes = pred["pred_boxes"].detach().cpu().numpy().tolist()
            scores = pred["pred_scores"].detach().cpu().numpy().tolist()
            labels = pred["pred_labels"].detach().cpu().numpy().tolist()
            label_names = [cfg.CLASS_NAMES[i - 1] for i in labels]

            record = {
                "frame_id": idx,
                "boxes_lidar": boxes,
                "scores": scores,
                "labels": label_names,
            }
            f.write(json.dumps(record) + "\n")
            processed += 1
            if args.log_interval and processed % args.log_interval == 0:
                logger.info(f"Processed {processed} frames")

    logger.info(f"Wrote predictions to {out_path}")


if __name__ == "__main__":
    main()
