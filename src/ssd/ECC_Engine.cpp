#include "ECC_Engine.h"
#include <cmath>

namespace SSD_Components
{
	ECC_Engine::ECC_Engine(double base_rber, double read_factor, double erase_factor,
		unsigned int page_size_in_bits, unsigned int correction_capability,
		sim_time_type decode_latency, unsigned int max_retries)
		: base_rber(base_rber), read_factor(read_factor), erase_factor(erase_factor),
		page_size_in_bits(page_size_in_bits), correction_capability(correction_capability),
		decode_latency(decode_latency), max_retries(max_retries)
	{
	}

	double ECC_Engine::Calculate_RBER(unsigned int read_count, unsigned int erase_count)
	{
		return base_rber + read_factor * read_count + erase_factor * erase_count;
	}

	int ECC_Engine::Attempt_correction(unsigned int read_count, unsigned int erase_count)
	{
		double rber = Calculate_RBER(read_count, erase_count);
		double expected_errors = rber * page_size_in_bits;

		// First-pass hard decode: can correct up to correction_capability errors
		if (expected_errors <= correction_capability) {
			return 0; // Success on first pass
		}

		// Soft-decode retries: each retry increases effective correction capability
		// by ~50% of the base capability (modeling soft-decision LDPC decoding)
		for (unsigned int retry = 1; retry <= max_retries; retry++) {
			double effective_capability = correction_capability * (1.0 + 0.5 * retry);
			if (expected_errors <= effective_capability) {
				return (int)retry;
			}
		}

		return -1; // Uncorrectable
	}

	sim_time_type ECC_Engine::Get_ECC_latency(int retry_count)
	{
		if (retry_count < 0) {
			// Uncorrectable: still incurred all retry attempts
			return decode_latency * (1 + max_retries);
		}
		// Base decode + additional retries
		return decode_latency * (1 + (unsigned int)retry_count);
	}
}
