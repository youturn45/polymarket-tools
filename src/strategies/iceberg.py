"""Iceberg order strategy - splits large orders into smaller tranches."""

import random

from models.order import StrategyParams


class IcebergStrategy:
    """Implements iceberg order splitting with randomization."""

    def __init__(self, params: StrategyParams):
        """Initialize iceberg strategy.

        Args:
            params: Strategy parameters for tranche sizing
        """
        self.params = params

    def calculate_next_tranche_size(
        self,
        remaining_size: int,
        is_first_tranche: bool = False,
    ) -> int:
        """Calculate size of next tranche with randomization.

        Args:
            remaining_size: Shares remaining to be filled
            is_first_tranche: Whether this is the first tranche

        Returns:
            Tranche size as integer
        """
        if remaining_size <= 0:
            return 0

        # Use initial size for first tranche, otherwise use min size as base
        base_size = (
            self.params.initial_tranche_size if is_first_tranche else self.params.min_tranche_size
        )

        # Apply randomization
        randomization = self.params.tranche_randomization
        if randomization > 0:
            # Random factor between (1 - randomization) and (1 + randomization)
            random_factor = 1.0 + random.uniform(-randomization, randomization)
            tranche_size = int(base_size * random_factor)
        else:
            tranche_size = base_size

        # Enforce min/max bounds
        tranche_size = max(self.params.min_tranche_size, tranche_size)
        tranche_size = min(self.params.max_tranche_size, tranche_size)

        # Don't exceed remaining size
        tranche_size = min(tranche_size, remaining_size)

        return tranche_size

    def calculate_all_tranches(self, total_size: int) -> list[int]:
        """Calculate all tranche sizes for an order.

        Args:
            total_size: Total order size

        Returns:
            List of tranche sizes that sum to total_size
        """
        tranches = []
        remaining = total_size
        is_first = True

        while remaining > 0:
            tranche_size = self.calculate_next_tranche_size(remaining, is_first)
            tranches.append(tranche_size)
            remaining -= tranche_size
            is_first = False

        return tranches

    def calculate_inter_tranche_delay(self) -> float:
        """Calculate randomized delay between tranches.

        Returns:
            Delay in seconds (1-3s randomized)
        """
        # Random delay between 1 and 3 seconds
        return random.uniform(1.0, 3.0)
