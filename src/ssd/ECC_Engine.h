#ifndef ECC_ENGINE_H
#define ECC_ENGINE_H

#include "../sim/Sim_Defs.h"

namespace SSD_Components
{
	class ECC_Engine
	{
	public:
		ECC_Engine(double base_rber, double read_factor, double erase_factor,
			unsigned int page_size_in_bits, unsigned int correction_capability,
			sim_time_type decode_latency, unsigned int max_retries);

		// Returns the number of retries needed (0 = first pass success).
		// Returns -1 if uncorrectable after all retries.
		int Attempt_correction(unsigned int read_count, unsigned int erase_count);

		// Returns total ECC decode latency in nanoseconds based on retry count.
		// retry_count=0 means first-pass decode; each retry adds decode_latency.
		sim_time_type Get_ECC_latency(int retry_count);

	private:
		double base_rber;        // Base raw bit error rate for fresh flash
		double read_factor;      // RBER increase per read (read disturb)
		double erase_factor;     // RBER increase per P/E cycle
		unsigned int page_size_in_bits;
		unsigned int correction_capability; // Max correctable bit errors per page
		sim_time_type decode_latency;       // Latency per decode attempt (ns)
		unsigned int max_retries;           // Max soft-decode retries before failure

		double Calculate_RBER(unsigned int read_count, unsigned int erase_count);
	};
}

#endif // !ECC_ENGINE_H
