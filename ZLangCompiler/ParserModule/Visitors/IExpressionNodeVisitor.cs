using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;

namespace ParserModule.Visitors;

public interface IExpressionNodeVisitor
{
    void VisitBinary(BinaryExpressionNode binaryExpression);
    void VisitUnary(UnaryExpressionNode unaryExpression);
    void VisitLiteralInteger(LiteralIntegerExpressionNode literalIntegerExpression);
    void VisitLiteralBool(LiteralBoolExpressionNode literalBoolExpression);
    void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode identifierExpression);
    void VisitFunctionCall(FunctionCallNode functionCallExpression);
}