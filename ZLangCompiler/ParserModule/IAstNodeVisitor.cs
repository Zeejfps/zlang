using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression);
    void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode);
    void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode);
}