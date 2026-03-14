// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title VulnerableVault — Demo 靶标合约，包含已知漏洞
/// @notice 用于 GoatGuard 审计 Agent 的现场演示
contract VulnerableVault {
    mapping(address => uint256) public balances;
    address public owner;
    bool private locked;

    constructor() {
        owner = msg.sender;
    }

    // [Critical] Reentrancy: 外部调用在状态更新之前
    function withdraw() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No balance");

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] = 0;
    }

    // [High] Missing access control: 任何人可以提走全部资金
    function emergencyDrain(address payable to) external {
        to.transfer(address(this).balance);
    }

    // [Medium] tx.origin authentication: 可被钓鱼合约利用
    modifier onlyOwner() {
        require(tx.origin == owner, "Not owner");
        _;
    }

    // [Low] Missing event emission: 关键操作缺少事件
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    // [Info] Missing zero-address check
    function transferOwnership(address newOwner) external onlyOwner {
        owner = newOwner;
    }

    receive() external payable {}
}
