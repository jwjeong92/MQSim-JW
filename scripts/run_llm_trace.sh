NUM_GEN_TOK=$1
DEVCONF="devconf/ssdconfig.xml"
WKDCONF="wkdconf/trace_llm.xml"
OUTDIR="results/llm_gen_${NUM_GEN_TOK}_tok.xml"
./mqsim -i $DEVCONF -w $WKDCONF -o $OUTDIR