class EthAccount:
    def __init__(self, eth_balance=0):
        self.eth_balance = eth_balance

    def transfer(self, to, eth):
        assert self.eth_balance >= eth
        self.eth_balance -= eth
        to.eth_balance += eth


class Player(EthAccount):
    def __init__(self, name, eth_balance):
        super().__init__(eth_balance)
        self.name = name
        self.token_balance = 0
        print(f"Here borns {self.__repr__()}")

    def __repr__(self):
        return f"😁 {self.name}\tETH: {self.eth_balance:.2f}\tToken: {self.token_balance:.2f}"


class ICOAddressData:
    def __init__(self, player):
        self.player = player
        self.name = player.name
        self.status = "inactive"
        self.balance = 0  # token balance
        self.cap = 0
        self.v = 0  # eth balance

    @property
    def isActive(self):
        return self.status == "active"

    def __repr__(self):
        face_of = {
            "active": "😁",
            "inactive": "😴",
            "used": "😥"
        }

        return f"{face_of[self.status]} {self.name}\tETH: {self.v:.2f}\tToken: {self.balance:.2f}\tCap: {self.cap}"


class ICOContract(EthAccount):
    def __init__(self, t, u, block_number):
        super().__init__()
        self.deployed_at = block_number
        self.t = t + block_number  # withdrawal lock
        self.u = u + block_number
        self.s = 0 + block_number
        self.addresses = {}

    def register(self, player):
        address = ICOAddressData(player)
        self.addresses[address.name] = address

    @property
    def inflation_ramp(self):
        # be a positive-valued, decreasing function
        # representing the purchase power of a native token at stage s.

        # Inflation ramp: Buyers who purchase tokens early receive a discounted
        # price. The maximum bonus might be 20% (a typical amount for
        # crowdsales today). The bonus decreases smoothly down to 10% at
        # the beginning of the withdrawal lock, and then disappears to nothing
        # by the end of the crowdsale.
        if self.s <= self.t:
            p = 0.8 + 0.1 * (self.s / self.t)
        elif self.t < self.s <= self.u:
            p = 0.9 + 0.1 * ((self.s - self.t) / (self.u - self.t))
        else:
            p = 1
        return p

    @property
    def crowdsale_valuation(self):
        # V: crowdsale valuation at the present instant as follows.
        active_address_values = [a.v for a in self.active_addresses]
        V = sum(active_address_values) if len(active_address_values) > 0 else 0
        return V

    @property
    def active_addresses(self):
        return [address for address in self.addresses.values() if address.isActive]

    def main_loop(self):
        self.automatic_withdrawal()

    def final_stage(self):
        for k, address in self.addresses.items():
            print(address)

    def receive_bids(self, player, eth, personal_cap):
        # 1. Any “inactive” address A may send to the crowdfund smart
        # contract:
        #   – a positive quantity of native tokens v(A) along with
        #   – a positive-valued personal cap c(A) > V .
        # 2. The smart contract then
        #   – sets the address balance b(A) = v(A) · p(s), effectively
        #     implementing the inflation ramp (Section 2), and
        #   – sets A’s status to “active.”
        assert personal_cap > self.crowdsale_valuation

        address_name = player.name

        player.transfer(self, eth)
        self.addresses[address_name].cap = personal_cap
        self.addresses[address_name].balance = eth * self.inflation_ramp
        self.addresses[address_name].status = "active"

    def voluntary_withdrawal(self, address_name):
        # The following only applies prior to the withdrawal lock at time t.
        # Any “active” address A may signal that it wishes to cancel its
        # bid from any previous stage. Upon such signal, the crowdfund
        # smart contract does the following:
        # 1. refunds v(A) native tokens back to A, and
        # 2. sets A’s status to “used.”
        assert self.s <= self.u

        self.addresses[address_name].balance = 0  # TODO: real refund
        self.addresses[address_name].status = "used"

    def automatic_withdrawal(self):
        while any([self.crowdsale_valuation > a.cap for a in self.active_addresses]):
            min_cap = min([a.cap for a in self.active_addresses])
            Bs = [a for a in self.active_addresses if a.cap == min_cap]
            S = sum([Bi.v for Bi in Bs])
            if self.crowdsale_valuation - S >= min_cap:
                for address in Bs:
                    print(f"💸 Refund {address.name} {address.v} eth")
                    self.transfer(address.player, address.v)
                    address.v = 0
                    address.status = "used"
            else:
                q = (self.crowdsale_valuation - min_cap) / S
                for address in Bs:
                    refund = q * address.v
                    self.transfer(address.player, refund)
                    address.balance *= (1 - q)
                    address.v *= (1 - q)

    def called_by_oracle(self, block_number):
        if self.s < self.u:
            self.automatic_withdrawal()
        elif self.s == self.t:
            print("!!!! t passed: withdrawal lock activated")
        elif self.s == self.u:
            print("!!!! u passed: token sales ended")
            self.final_stage()

        self.s = block_number - self.deployed_at

    def __repr__(self):
        return f"⏲️ {self.s}\tV: {self.crowdsale_valuation}\tp: {self.inflation_ramp}"


class Chain:
    def __init__(self):
        self.block_number = 0
        self.contract = None

    def mine_a_block(self):
        self.contract.called_by_oracle(self.block_number)
        self.block_number += 1

    def mine(self, blocks):
        for b in range(blocks):
            self.mine_a_block()
        print(f"# {self.block_number}: 🆙 mined {blocks} blocks!")


if __name__ == "__main__":

    print("# case 1")
    c = Chain()
    a = Player("Alice", 100)
    b = Player("Bob", 200)
    contract = ICOContract(50, 100, c.block_number)
    contract.register(a)
    contract.register(b)
    c.contract = contract
    c.mine(10)
    contract.receive_bids(a, 30, 79)
    c.mine(20)
    contract.receive_bids(b, 30, 79)
    c.mine(100)
