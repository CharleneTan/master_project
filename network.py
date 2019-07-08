# -*- coding: utf-8 -*-

import time
import random
from .datatype import Vin,Vout,Tx,Block,get_merkle_root_of_txs
from .logger import logger
from .peer import Peer,find_utxos_from_block,add_utxos_to_set

from .consensus import consensus_with_fasttest_minner
from .params import Params
from math import ceil
from itertools import accumulate
from .connectDB import SQL
import json


#Class p2p Network 
# =============================================================================

class Network(object):

    def __init__(self,nop = None,von = None):
        
        self.peers = []
        self.off_peers = []
        self.consensus_peers = []
        self.current_winner = None
        self.winner = []
        self.init_peers_number = nop or Params.INIT_NUMBER_OF_PEERS
        self.init_value = von or Params.INIT_COIN_PER_PEER
        self.create_genesis_block(self.init_peers_number,self.init_value)
        self.time_spent = [0]
        
        self._is_consensus_peers_chosen = False
        self._not = 0
        self.tx_count = 0

    
    def init_peers(self,number):
        for _ in range(number):
            coords = generate_random_coords()
            peer = Peer(coords)
            create_peer(self,peer)
    
    def add_peer(self):
        coords = generate_random_coords()
        peer = Peer(coords)
        create_peer(self,peer)
        # self.generate_btc_to_peers(peer,Params.INIT_COIN_PER_PEER)
        peer.update_blockchain(self.peers[0])
        peer.update_mem_pool(self.peers[0])
        peer.update_utxo_set(self.peers[0])
        logger.info('A new peer joined in --> {0}(pid={1})'.format(peer,peer.pid))

    def add_random_peers(self):
        # random_add = random.randint(1, Params.RANDOM_PEERS_NUM)
        random_add = 100
        for i in range(random_add):
            self.add_peer()

    def generate_btc_to_peers(self,peer,value):
        tx_in = [Vin(to_spend=None,
                     signature=b'I love blockchain',
                     pubkey=None)]

        tx_out = [Vout(value=value, to_addr=peer.wallet.addrs[-1])]

        txs = [Tx(tx_in=tx_in, tx_out=tx_out, nlocktime=0)]
        genesis_block = Block(version=0,
                              prev_block_hash=None,
                              timestamp=841124,
                              bits=0,
                              nonce=0,
                              txs=txs)

        utxos = find_utxos_from_block(txs)
        for p in self.peers:
            p.blockchain.append(genesis_block)
            add_utxos_to_set(p.utxo_set, utxos)

        tout = [tx_out[0].to_json()]
        tin = []
        keys = ["input", "output"]
        values = [tin, tout]
        d = dict(zip(keys, values))
        j = json.dumps(d)

        db = SQL()
        sql = """INSERT INTO `transactions` (`tx`) VALUES (%s)"""
        input_tuple = (j)
        db.query(sql, input_tuple)
        db.commit()
        db.close()

    def create_genesis_block(self,number,value):
        self.init_peers(number = number)
        tx_in =[Vin(to_spend = None,
                    signature = b'I love blockchain',
                    pubkey = None)]
        
        tx_out = [Vout(value = value,to_addr = peer.wallet.addrs[-1])
                  for peer in self.peers]
        
        
        txs = [Tx(tx_in = tx_in,tx_out = tx_out,nlocktime = 0)]
        genesis_block = Block(version=0,
                              prev_block_hash=None,
                              timestamp = 841124,
                              bits = 0,
                              nonce = 0,
                              txs = txs)
        re = []
        for i in tx_out:
            tout = [i.to_json()]
            tin = []
            keys = ["input", "output"]
            values = [tin, tout]
            d = dict(zip(keys, values))
            j = json.dumps(d)
            re.append(j)

        db = SQL()
        sql = """INSERT INTO `transactions` (`tx`) VALUES (%s)"""
        input_tuple = tuple(re)
        db.querymany(sql, input_tuple)
        db.commit()
        db.close()

        logger.info('A blockchain p2p network created,{0} peers joined'.format(self.nop))
        logger.info('genesis block has been generated')
        
        utxos = find_utxos_from_block(txs)
        for peer in self.peers:
            peer.blockchain.append(genesis_block)
            add_utxos_to_set(peer.utxo_set,utxos)
        
            
    def make_random_transactions(self):
        # k = random.randint(1,self.nop)
        k = random.randint(1, 200)
        self._not = k
        for _ in range(k):
            sender = random.choice(self.peers[1:])
            receiver = random.choice(self.peers[1:])
            if receiver.pid == sender.pid:
                continue
            sender.create_transaction(receiver,
                                      tx_random_value_for_sender(sender))
            
            sender.broadcast_transaction()

    def set_consensus_peers(self,*idx):
        for i in idx:
            self.consensus_peers.append(self.peers[i])
            
        self._is_consensus_peers_chosen = True
    
    def choose_random_consensus_peers(self):
        n = self.nop
        #we suppose we have 20%~60% nodes are consensus node
        ub,lb = Params.UPPER_BOUND_OF_CONSENSUS_PEERS,\
                Params.LOWWER_BOUND_OF_CONSENSUS_PEERS
        k = random.randint(ceil(lb*n),ceil(ub*n))
        self.consensus_peers = random.sample(self.peers,k)     
        self._is_consensus_peers_chosen = True
        
        
    def consensus(self,meth = 'pow'):
        if not self._is_consensus_peers_chosen:
            self.choose_random_consensus_peers()
        
        if meth == 'pow':
            logger.info('{0} peers are mining'.format(len(self.consensus_peers)))
            n,nonce,time = consensus_with_fasttest_minner(self.consensus_peers)
            self.time_spent.append(time)
            self.current_winner = self.consensus_peers[n]
            self.winner.append(self.current_winner)

            block = self.current_winner.package_block(nonce = nonce)

            self.current_winner.recieve_block(block)
            self.current_winner.broadcast_block(block)

            logger.info('{0}(pid={1}) is winner,{2} secs used'.format(
                self.current_winner,
                self.current_winner.pid,
                time
            ))

            # database execution
            self.insert_database(block)
            self.tx_count = self.tx_count + len(block.txs)


    # insert txs into database
    def insert_database(self,block):

        db = SQL()
        sql = """INSERT INTO `transactions` (`tx`) VALUES (%s)"""

        # store mining transaction
        tin = []
        tout = [block.txs[0].tx_out[0].to_json()]
        keys = ["input", "output"]
        values = [tin, tout]
        d = dict(zip(keys, values))
        j = json.dumps(d)
        input_tuple = j
        db.query(sql, input_tuple)

        # store other transactions
        re = []
        for i, tx in enumerate(block.txs):
            tout = [t_out.to_json() for t_out in tx.tx_out]
            tin = []
            t_in = tx.tx_in
            for vin in t_in:
                if not vin.to_spend:
                    pass
                else:
                    pointer = vin.to_spend
                    for u in self.peers[0]._utxos_from_vins:
                        if pointer.tx_id == list(u)[1].tx_id and pointer.n == list(u)[1].n:
                            tin.append(list(u)[0].to_json())

            keys = ["input", "output"]
            values = [tin, tout]
            d = dict(zip(keys, values))
            j = json.dumps(d)
            re.append(j)

        db = SQL()
        sql = """INSERT INTO `transactions` (`tx`) VALUES (%s)"""
        input_tuple = tuple(re)
        db.querymany(sql, input_tuple)
        db.commit()
        db.close()



    def draw(self):
        pass
    
    @property
    def time(self):
        return _accumulate(self.time_spent)

    def get_time(self):
        return self.time[-1]
 
    @property
    def nop(self):
        return len(self.peers)

    def __repr__(self):
        return 'A p2p blockchain network with {0} peers'.format(self.nop)

def create_peer(net,peer):
    peer.pid = net.nop
    peer.network = net
    peer.wallet.generate_keys()
    net.peers.append(peer)


#functions
# =============================================================================



#Iterables 
# =============================================================================
    


def addr_finder(tx):
    return (out.vout.to_addr for out in tx.tx_out)

def _accumulate(l):
    return list(accumulate(l))
    
#random data
# =============================================================================

def tx_random_value():
    return random.randint(0,100)

def tx_random_value_for_sender(peer):
    v = random.randint(0,peer.get_balance())
    v_1 = int(v / 100)
    if v_1 == 0:
        value = 100
    else:
        value = v_1 * 100
    return value

def generate_random_coords():
    return (random.randint(0,100),random.randint(0,100))

    
if __name__ == "__main__":
    pass

##    net = Network(nop = 2,von = 10000)
##    
##    zhangsan,lisi = net.peers[0],net.peers[1]
##    zhangsan.create_transaction(lisi.wallet.addrs[0],100)
##    zhangsan.broadcast_transaction()
##    lisi.create_transaction(zhangsan.wallet.addrs[0],100)
##    lisi.broadcast_transaction()
    
##
    net = Network()
    net.make_random_transactions()
    net.consensus()
##    b = zhangsan.get_utxo()[0]
##    print(b.pubkey_script)
##    tx = zhangsan.current_tx
##    vin = tx.tx_in[0]
##    vin1 = Vin(vin.to_spend,b'1'*64,vin.pubkey)
##    tx.tx_in[0] = vin1
##    lisi.mem_pool = {}
##    lisi.verify_transaction(tx,lisi.mem_pool)
    
    
##    
##    
##    for _ in range(4):
##        net.make_random_transactions()
##        net.consensus()



        

