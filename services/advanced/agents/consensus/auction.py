"""
Resource Auction - Market-based resource allocation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging
import heapq

logger = logging.getLogger(__name__)


class AuctionType(Enum):
    """Types of auctions."""
    FIRST_PRICE = "first_price"      # Highest bidder pays their bid
    SECOND_PRICE = "second_price"    # Highest bidder pays second highest bid
    DUTCH = "dutch"                   # Descending price
    VICKREY = "vickrey"               # Sealed-bid second-price


@dataclass
class Resource:
    """Resource being auctioned."""
    resource_id: str
    resource_type: str
    capacity: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Bid:
    """Agent bid on a resource."""
    agent_id: str
    resource_id: str
    price: float
    quantity: float = 1.0
    priority: int = 5
    constraints: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other: 'Bid') -> bool:
        """Compare bids by price (descending) then priority."""
        return (-self.price, self.priority, self.timestamp) < (-other.price, other.priority, other.timestamp)


@dataclass
class AuctionResult:
    """Result of an auction."""
    auction_id: str
    resource_id: str
    winner_id: Optional[str]
    winning_price: float
    all_bids: List[Bid]
    cleared: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ResourceAuction:
    """
    Market-based resource allocation through auctions.

    Used for allocating:
    - Printer time slots
    - Material batches
    - Quality inspection resources
    - Compute resources for simulation

    Features:
    - Multiple auction types
    - Multi-unit auctions
    - Combinatorial bidding
    - Reserve prices
    """

    def __init__(self, auction_type: AuctionType = AuctionType.SECOND_PRICE):
        self.auction_type = auction_type
        self._active_auctions: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, AuctionResult] = {}

    def create_auction(self,
                       auction_id: str,
                       resource: Resource,
                       reserve_price: float = 0.0,
                       min_increment: float = 0.01) -> str:
        """
        Create a new auction.

        Args:
            auction_id: Unique auction identifier
            resource: Resource being auctioned
            reserve_price: Minimum acceptable price
            min_increment: Minimum bid increment

        Returns:
            Auction ID
        """
        self._active_auctions[auction_id] = {
            'resource': resource,
            'reserve_price': reserve_price,
            'min_increment': min_increment,
            'bids': [],
            'created_at': datetime.utcnow(),
            'status': 'open'
        }

        logger.info(f"Created auction {auction_id} for resource {resource.resource_id}")
        return auction_id

    def place_bid(self, auction_id: str, bid: Bid) -> bool:
        """
        Place a bid on an auction.

        Args:
            auction_id: Auction identifier
            bid: Bid to place

        Returns:
            True if bid accepted
        """
        if auction_id not in self._active_auctions:
            logger.warning(f"Auction {auction_id} not found")
            return False

        auction = self._active_auctions[auction_id]
        if auction['status'] != 'open':
            logger.warning(f"Auction {auction_id} is not open")
            return False

        if bid.price < auction['reserve_price']:
            logger.debug(f"Bid below reserve price: {bid.price} < {auction['reserve_price']}")
            return False

        # Check minimum increment if not first bid
        if auction['bids']:
            current_high = max(b.price for b in auction['bids'])
            if bid.price <= current_high:
                if bid.price < current_high + auction['min_increment']:
                    return False

        heapq.heappush(auction['bids'], bid)
        logger.debug(f"Agent {bid.agent_id} bid {bid.price} on auction {auction_id}")
        return True

    def close_auction(self, auction_id: str) -> Optional[AuctionResult]:
        """
        Close an auction and determine winner.

        Args:
            auction_id: Auction identifier

        Returns:
            AuctionResult or None
        """
        if auction_id not in self._active_auctions:
            return None

        auction = self._active_auctions[auction_id]
        auction['status'] = 'closed'

        bids = sorted(auction['bids'])
        if not bids:
            result = AuctionResult(
                auction_id=auction_id,
                resource_id=auction['resource'].resource_id,
                winner_id=None,
                winning_price=0,
                all_bids=[],
                cleared=False
            )
        else:
            winner = bids[0]

            # Determine price based on auction type
            if self.auction_type == AuctionType.FIRST_PRICE:
                winning_price = winner.price
            elif self.auction_type in (AuctionType.SECOND_PRICE, AuctionType.VICKREY):
                winning_price = bids[1].price if len(bids) > 1 else auction['reserve_price']
            else:
                winning_price = winner.price

            result = AuctionResult(
                auction_id=auction_id,
                resource_id=auction['resource'].resource_id,
                winner_id=winner.agent_id,
                winning_price=winning_price,
                all_bids=bids,
                cleared=True
            )

        self._results[auction_id] = result
        del self._active_auctions[auction_id]

        logger.info(f"Auction {auction_id} closed: winner={result.winner_id}, price={result.winning_price}")
        return result

    def get_current_high_bid(self, auction_id: str) -> Optional[float]:
        """Get current highest bid for an auction."""
        if auction_id not in self._active_auctions:
            return None
        bids = self._active_auctions[auction_id]['bids']
        if not bids:
            return None
        return max(b.price for b in bids)

    def get_auction_status(self, auction_id: str) -> Optional[Dict[str, Any]]:
        """Get auction status."""
        if auction_id in self._active_auctions:
            auction = self._active_auctions[auction_id]
            return {
                'status': auction['status'],
                'resource_id': auction['resource'].resource_id,
                'bid_count': len(auction['bids']),
                'high_bid': self.get_current_high_bid(auction_id),
                'reserve_price': auction['reserve_price']
            }
        elif auction_id in self._results:
            result = self._results[auction_id]
            return {
                'status': 'closed',
                'resource_id': result.resource_id,
                'winner': result.winner_id,
                'winning_price': result.winning_price
            }
        return None

    def get_result(self, auction_id: str) -> Optional[AuctionResult]:
        """Get result of a closed auction."""
        return self._results.get(auction_id)


class CombinatorialAuction(ResourceAuction):
    """
    Combinatorial auction for bundled resources.

    Allows bidding on combinations of resources.
    """

    def __init__(self):
        super().__init__(AuctionType.FIRST_PRICE)
        self._bundle_bids: Dict[str, List[Dict]] = {}

    def place_bundle_bid(self,
                         auction_id: str,
                         agent_id: str,
                         resource_ids: List[str],
                         price: float) -> bool:
        """
        Place a bid on a bundle of resources.

        The bid is only valid if the agent wins all resources.
        """
        if auction_id not in self._bundle_bids:
            self._bundle_bids[auction_id] = []

        self._bundle_bids[auction_id].append({
            'agent_id': agent_id,
            'resources': set(resource_ids),
            'price': price,
            'timestamp': datetime.utcnow()
        })
        return True

    def solve_combinatorial(self, auction_id: str) -> Dict[str, str]:
        """
        Solve winner determination problem.

        Uses greedy approximation for NP-hard problem.

        Returns:
            Mapping of resource_id to winner agent_id
        """
        if auction_id not in self._bundle_bids:
            return {}

        bids = self._bundle_bids[auction_id]
        bids.sort(key=lambda b: -b['price'])  # Sort by price descending

        allocated = set()
        winners = {}

        for bid in bids:
            if not bid['resources'] & allocated:  # No conflict
                for resource_id in bid['resources']:
                    winners[resource_id] = bid['agent_id']
                    allocated.add(resource_id)

        return winners
