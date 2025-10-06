using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression);
    void VisitLiteralBoolExpression(LiteralBoolExpressionNode literalBoolExpressionNode);
    void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode);
    void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode);
    void VisitIdentifierExpression(IdentifierExpressionNode identifierExpressionNode);
}