"""Storage engine for batch buffering and atomic writing to Parquet and CSV datasets."""

from pathlib import Path
from typing import Literal, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

from src.models.dataset_models import MLParticipantRecord


class BatchStorage:
    """Buffers participant records and safely flushes them to disk."""

    def __init__(
        self,
        data_dir: Path,
        output_format: Literal["parquet", "csv", "both"] = "parquet",
        batch_size_matches: int = 50,
        dataset_name: str = "ranked_matches",
    ) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_format = output_format
        self.batch_size_rows = batch_size_matches * 10
        self.dataset_name = dataset_name

        self.parquet_path = self.data_dir / f"{dataset_name}.parquet"
        self.csv_path = self.data_dir / f"{dataset_name}.csv"

        self._buffer: list[MLParticipantRecord] = []
        self._total_rows_written: int = 0

        # Initialize existing row count if files exist
        if self.parquet_path.exists():
            try:
                table = pq.read_table(self.parquet_path)
                self._total_rows_written = table.num_rows
                logger.info(f"Existing Parquet dataset found with {self._total_rows_written} rows.")
            except Exception as err:
                logger.warning(f"Could not read existing Parquet row count: {err}")

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    @property
    def total_rows(self) -> int:
        return self._total_rows_written + len(self._buffer)

    def add_records(self, records: list[MLParticipantRecord]) -> None:
        """Add participant records to the buffer. Flushes automatically if batch size reached."""
        self._buffer.extend(records)
        if len(self._buffer) >= self.batch_size_rows:
            self.flush()

    def flush(self) -> int:
        """Flush all buffered records to disk atomically."""
        if not self._buffer:
            return 0

        flushed_count = len(self._buffer)
        dicts = [record.model_dump() for record in self._buffer]
        new_df = pd.DataFrame(dicts)

        # Write Parquet
        if self.output_format in ("parquet", "both"):
            self._write_parquet(new_df)

        # Write CSV
        if self.output_format in ("csv", "both"):
            self._write_csv(new_df)

        self._total_rows_written += flushed_count
        self._buffer.clear()
        logger.info(
            f"Flushed {flushed_count} rows to disk. Total records in dataset: {self._total_rows_written}."
        )
        return flushed_count

    def _write_parquet(self, df: pd.DataFrame) -> None:
        """Write DataFrame to Parquet dataset atomically."""
        new_table = pa.Table.from_pandas(df, preserve_index=False)
        temp_file = self.parquet_path.with_suffix(".tmp")

        if self.parquet_path.exists():
            try:
                existing_table = pq.read_table(self.parquet_path)
                combined_table = pa.concat_tables([existing_table, new_table])
            except Exception as err:
                logger.error(f"Error reading existing Parquet for concatenation: {err}")
                combined_table = new_table
        else:
            combined_table = new_table

        pq.write_table(combined_table, temp_file, compression="snappy")
        temp_file.replace(self.parquet_path)

    def _write_csv(self, df: pd.DataFrame) -> None:
        """Append DataFrame to CSV file."""
        header = not self.csv_path.exists()
        df.to_csv(self.csv_path, mode="a", header=header, index=False)

    def export_to_csv(self, output_path: Optional[Path] = None) -> Path:
        """Export full Parquet dataset to CSV for spreadsheet inspection."""
        target_path = output_path or self.csv_path
        if not self.parquet_path.exists():
            raise FileNotFoundError(f"No Parquet dataset found at {self.parquet_path}")

        df = pd.read_parquet(self.parquet_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target_path, index=False)
        logger.info(f"Successfully exported {len(df)} rows from Parquet to {target_path}")
        return target_path

    def filter_and_export(
        self,
        output_path: Optional[Path] = None,
        output_format: Literal["parquet", "csv", "both"] = "csv",
        input_path: Optional[Path] = None,
        champions: Optional[list[str]] = None,
        positions: Optional[list[str]] = None,
        side: Optional[str] = None,
        win: Optional[int] = None,
        patch_prefix: Optional[str] = None,
        min_duration_sec: Optional[int] = None,
        max_duration_sec: Optional[int] = None,
    ) -> tuple[int, list[Path]]:
        """Filter an existing dataset on disk and export matching rows."""
        source_path = input_path or self.parquet_path
        if not source_path.exists():
            raise FileNotFoundError(f"No dataset found at {source_path}")

        if source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path)
        else:
            df = pd.read_parquet(source_path)

        if champions:
            target_champions = {c.strip().lower() for c in champions if c.strip()}
            if target_champions:
                df = df[df["champion_name"].astype(str).str.lower().isin(target_champions)]

        if positions:
            target_positions = {pos.strip().upper() for pos in positions if pos.strip()}
            if target_positions:
                df = df[df["team_position"].astype(str).str.upper().isin(target_positions)]

        if side:
            df = df[df["side"].astype(str).str.upper() == side.strip().upper()]

        if win is not None:
            df = df[df["win"] == win]

        if patch_prefix:
            df = df[df["game_version"].astype(str).str.startswith(patch_prefix.strip())]

        if min_duration_sec is not None:
            df = df[df["game_duration"] >= min_duration_sec]

        if max_duration_sec is not None:
            df = df[df["game_duration"] <= max_duration_sec]

        default_ext = ".parquet" if output_format == "parquet" else ".csv"
        base_output = output_path or (self.data_dir / f"filtered_matches{default_ext}")
        base_output.parent.mkdir(parents=True, exist_ok=True)

        written_paths: list[Path] = []
        if output_format in ("parquet", "both"):
            parquet_target = (
                base_output if base_output.suffix.lower() == ".parquet" else base_output.with_suffix(".parquet")
            )
            table = pa.Table.from_pandas(df, preserve_index=False)
            tmp_parquet = parquet_target.with_suffix(".tmp")
            pq.write_table(table, tmp_parquet, compression="snappy")
            tmp_parquet.replace(parquet_target)
            written_paths.append(parquet_target)

        if output_format in ("csv", "both"):
            csv_target = (
                base_output if base_output.suffix.lower() == ".csv" else base_output.with_suffix(".csv")
            )
            df.to_csv(csv_target, index=False)
            written_paths.append(csv_target)

        logger.info(
            f"Filtered dataset exported: {len(df)} rows written to {[str(p) for p in written_paths]}"
        )
        return len(df), written_paths
