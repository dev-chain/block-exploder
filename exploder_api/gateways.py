import pymongo
MAIN_CHAIN = 'main_chain'


class DatabaseGateway(object):
    def __init__(self, database):
        self.blocks = database.blocks
        self.transactions = database.transactions
        self.vin = database.vin
        self.vout = database.vout

    def get_latest_blocks(self, limit=25, offset=0):
        return list(self.blocks.find({"chain": MAIN_CHAIN})
                    .sort("height", pymongo.DESCENDING).skip(offset).limit(limit))

    def get_block_by_hash(self, hash):
        block = self.blocks.find_one({"hash": hash})
        if block:
            return block
        raise KeyError("Block not found")

    def get_block_by_height(self, height):
        block = self.blocks.find_one({"height": height})
        if block:
            return block
        raise KeyError("Block not found")

    def get_address_unspent(self, address):
        vouts = self.vout.find({"address": address})

        if not vouts:
            return []

        unspent_vouts = []

        for vout in vouts:
            spent = self.vin.find_one({"prev_txid": vout["txid"], "vout_index": vout["index"]})

            if not spent:
                unspent_vouts.append(vout)

        return unspent_vouts

    def get_address_statistics(self, address):
        vouts = list(self.vout.find({"address": address}))
        volume = sum([vout["value"] for vout in vouts])
        txids = [v['txid'] for v in vouts]
        return list(self.transactions.find({"txid": {"$in": txids}})), volume

    def get_transaction_by_txid(self, txid):
        tr = self.transactions.find_one({"txid": txid})

        if not tr:
            raise KeyError("Transaction with txid %s doesn't exist in the database" % txid)

        tr_block = self.get_block_by_hash(tr["blockhash"])
        tr['confirmations'] = self.calculcate_block_confirmations(tr_block)

        return tr

    def get_transactions_by_blockhash(self, blockhash):
        tr = self.transactions.find({"blockhash": blockhash})

        if not tr:
            raise KeyError("Block with hash %s doesn't exist in the database" % blockhash)

        return list(tr)

    def get_network_hash_rate(self):
        highest = self.get_highest_in_chain(MAIN_CHAIN)
        end = highest['time']
        start = highest['time'] - 86400
        blocks_in_interval = self.blocks.find({"time": {"$gt": start, "$lt": end}})
        cum_work = sum([block['work'] for block in blocks_in_interval])
        hps = float(cum_work) / 86400

        if hps >= 10e8:
            return {
                "rate": int(hps / 10e8),
                "unit": "GH/s"
            }
        elif hps >= 10e5:
            return {
                "rate": int(hps / 10e5),
                "unit": "MH/s"
            }
        else:
            return {
                "rate": int(hps),
                "unit": "H/s"
            }

    def get_highest_in_chain(self, chain):
        return self.blocks.find_one({"chain": chain}, sort=[("height", -1)])

    def calculcate_block_confirmations(self, block):
        highest_in_chain = self.get_highest_in_chain(block['chain'])
        return highest_in_chain['height'] - block['height']