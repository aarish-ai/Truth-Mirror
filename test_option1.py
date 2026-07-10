import logging
logging.basicConfig(level=logging.INFO)
from truth_mirror.claim_scope_gate import gate_claim
from truth_mirror.local_decomposer import LocalDecomposer
from truth_mirror.geo_query_generator import GeoQueryGenerator

print("Testing Option 1...")
res1 = gate_claim("US invaded Venezuela")
print("Gate Result:", res1)

dec = LocalDecomposer()
res2 = dec.decompose("US invaded Venezuela")
print("Decompose Result:", res2)

gen = GeoQueryGenerator()
res3 = gen.generate("US invaded Venezuela", ["US", "Venezuela"], "military")
print("Generate Result:", res3)
