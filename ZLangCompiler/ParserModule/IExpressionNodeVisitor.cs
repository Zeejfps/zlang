using ParserModule.Nodes;

namespace ParserModule;

public interface IExpressionNodeVisitor
{
    void VisitBinaryExpression(BinaryExpressionNode node);
    void VisitUnaryExpression(UnaryExpressionNode node);
}