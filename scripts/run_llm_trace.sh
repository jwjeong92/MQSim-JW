NUM_GEN_TOK=$1
DEVCONF="devconf/ssdconfig.xml"
WKDCONF="wkdconf/trace_llm.xml"
TRACEFILE="traces/llama_7b_gen_${NUM_GEN_TOK}_tok.trace"
OUTDIR="results/llm_gen_${NUM_GEN_TOK}_tok.xml"

python lib/llm_trace_gen.py $NUM_GEN_TOK &&
mv "llama_7b_gen_${NUM_GEN_TOK}_tok.trace" ./traces &&
xmlstarlet ed -L -u "//File_Path" -v $TRACEFILE $WKDCONF &&

./mqsim -i $DEVCONF -w $WKDCONF -o $OUTDIR