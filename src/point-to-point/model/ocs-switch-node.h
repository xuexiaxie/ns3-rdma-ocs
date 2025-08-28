#ifndef OCS_SWITCH_NODE_H
#define OCS_SWITCH_NODE_H

#include <ns3/node.h>
#include <unordered_map>
#include <vector>
#include "qbb-net-device.h"

namespace ns3 {

class Packet;

/**
 * @brief Optical Circuit Switch Node
 * 
 * This class implements an optical circuit switch that provides
 * one-to-one port mapping without packet processing.
 * The switch only handles physical layer transmission.
 */
class OcsSwitchNode : public Node {
    static const unsigned pCnt = 128;  // Maximum number of ports

public:
    static TypeId GetTypeId(void);
    OcsSwitchNode();
    virtual ~OcsSwitchNode();

    /**
     * @brief Set port mapping table
     * @param portMapping Map from input port to output port
     */
    void SetPortMapping(const std::unordered_map<uint32_t, uint32_t>& portMapping);

    /**
     * @brief Update a single port mapping
     * @param inputPort Input port index
     * @param outputPort Output port index  
     */
    void UpdatePortMapping(uint32_t inputPort, uint32_t outputPort);

    /**
     * @brief Clear all port mappings
     */
    void ClearPortMapping();

    /**
     * @brief Get current port mapping
     */
    const std::unordered_map<uint32_t, uint32_t>& GetPortMapping() const;

    /**
     * @brief Handle packet reception from a device
     * @param device The receiving device
     * @param packet The received packet
     * @param protocol Protocol number
     * @param from Source address
     * @return true if packet was handled
     */
    bool OcsReceiveFromDevice(Ptr<NetDevice> device, Ptr<Packet> packet, 
                              uint16_t protocol, const Address& from);

private:
    /**
     * @brief Forward packet to mapped output port
     * @param inputPort Input port that received the packet
     * @param packet The packet to forward
     * @param protocol Protocol number
     */
    void ForwardPacket(uint32_t inputPort, Ptr<Packet> packet, uint16_t protocol);

    /**
     * @brief Get device index for a given NetDevice
     * @param device The NetDevice
     * @return Device index, or UINT32_MAX if not found
     */
    uint32_t GetDeviceIndex(Ptr<NetDevice> device) const;

    // Port mapping: input port -> output port
    std::unordered_map<uint32_t, uint32_t> m_portMapping;
    
    // Track packet statistics (optional)
    uint64_t m_totalPacketsForwarded;
    uint64_t m_totalBytesForwarded;
};

} // namespace ns3

#endif /* OCS_SWITCH_NODE_H */