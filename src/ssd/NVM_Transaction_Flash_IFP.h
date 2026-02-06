#ifndef NVM_TRANSACTION_FLASH_IFP_H
#define NVM_TRANSACTION_FLASH_IFP_H

#include "../nvm_chip/flash_memory/FlashTypes.h"
#include "NVM_Transaction_Flash.h"

namespace SSD_Components
{
	class NVM_Transaction_Flash_IFP : public NVM_Transaction_Flash
	{
	public:
		NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
			unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa,
			SSD_Components::User_Request* related_user_IO_request, NVM::memory_content_type content,
			page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp);
		NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
			unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa, const NVM::FlashMemory::Physical_Page_Address& address,
			SSD_Components::User_Request* related_user_IO_request, NVM::memory_content_type content,
			page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp);
		NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
			unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa,
			SSD_Components::User_Request* related_user_IO_request, IO_Flow_Priority_Class::Priority priority_class,
			NVM::memory_content_type content,
			page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp);

		NVM::memory_content_type Content;
		page_status_type read_sectors_bitmap;
		data_timestamp_type DataTimeStamp;
		double Partial_dot_product_result;
		bool ECC_retry_needed;
		unsigned int ECC_retry_count;
		bool Aggregation_complete;
	};
}

#endif // !NVM_TRANSACTION_FLASH_IFP_H
