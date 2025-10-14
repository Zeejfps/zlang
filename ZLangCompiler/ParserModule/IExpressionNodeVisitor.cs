using ParserModule.Nodes;

namespace ParserModule;

public interface IExpressionNodeVisitor
{
    void VisitBinary(BinaryExpressionNode node);
    void VisitUnary(UnaryExpressionNode node);
    void VisitLiteralInteger(LiteralIntegerExpressionNode node);
    void VisitLiteralBool(LiteralBoolExpressionNode node);
    void VisitIdentifier(IdentifierExpressionNode node);
}